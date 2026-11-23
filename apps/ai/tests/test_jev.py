"""
Jev client, tested offline on hand-written samples of the TypeSafe wire format (https://api.typesafe.ai/openapi.json):
httpx.MockTransport plays the API; we check the request we build and what we read back.
"""

import json

import httpx
import pytest

from app.agent.jev_examples import is_yes, pick_product
from app.clients.factory import make_jev_client
from app.clients.http import ProviderError
from app.clients.jev import JevClient, choice_question, score_question, yes_no_question
from app.config import JevSettings


def fake_jev(answers: dict | None = None, status: int = 200, body: str | None = None):
    """A JevClient whose HTTP calls are recorded and answered with a SystemOneResponse sample."""
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if body is not None:
            return httpx.Response(status, text=body)
        payload = {"model": "jev-2026-09-15", "answers": answers, "usage": {"input_tokens": 42, "output_tokens": 3}}
        return httpx.Response(status, json=payload)

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return JevClient("test-key", "jev-latest", "https://jev.test/", http=http), seen


def sent(seen: list[httpx.Request]) -> dict:
    return json.loads(seen[0].content)


async def test_choose_request_and_answer():
    jev, seen = fake_jev({"q": {"type": "choice", "choice": "prd_2", "confidence": 0.91, "probabilities": {"prd_1": 0.09, "prd_2": 0.91}}})
    d = await jev.choose("5 kilos de bar de ligne", "Quel produit ?", {"prd_1": "Bar d'élevage", "prd_2": "Bar de ligne"})

    req = seen[0]
    assert req.method == "POST" and str(req.url) == "https://jev.test/v1/systemone"
    assert req.headers["authorization"] == "Bearer test-key"
    assert sent(seen) == {
        "model": "jev-latest",
        "state": "5 kilos de bar de ligne",
        "questions": {"q": {"type": "choice", "instructions": "Quel produit ?", "criteria": {"prd_1": "Bar d'élevage", "prd_2": "Bar de ligne"}}},
    }
    assert (d.choice, d.confidence, d.probabilities) == ("prd_2", 0.91, {"prd_1": 0.09, "prd_2": 0.91})


async def test_score_and_yes_no():
    jev, seen = fake_jev({"q": {"type": "score", "score": 1.7, "confidence": 0.8, "legend": {"0": "a", "1": "b", "2": "c"}, "probabilities": {"0": 0.1, "1": 0.1, "2": 0.8}}})
    s = await jev.score({"message": "livraison en retard"}, "Urgence ?", ["peut attendre", "aujourd'hui", "tout de suite"])
    assert sent(seen)["questions"]["q"] == {"type": "score", "instructions": "Urgence ?", "criteria": ["peut attendre", "aujourd'hui", "tout de suite"]}
    assert sent(seen)["state"] == {"message": "livraison en retard"}
    assert (s.score, s.probabilities["2"]) == (1.7, 0.8)

    jev, seen = fake_jev({"q": {"type": "noul", "noul": 0.97}})
    assert await jev.yes_no("oui vas-y", "Le client confirme.", yes="accepte", no="refuse") == 0.97
    assert sent(seen)["questions"]["q"] == {"type": "noul", "instructions": "Le client confirme.", "criteria": {"true": "accepte", "false": "refuse"}}


def test_question_builders_match_the_wire_format():
    assert choice_question(None, ["billing", "other"]) == {"type": "choice", "criteria": {"billing": None, "other": None}}
    assert score_question("Note", ["bas", "haut"]) == {"type": "score", "instructions": "Note", "criteria": ["bas", "haut"]}
    assert yes_no_question("Spam ?") == {"type": "noul", "instructions": "Spam ?"}


async def test_raw_ask_several_questions_one_call():
    answers = {"intent": {"type": "choice", "choice": "commande", "confidence": 0.7, "probabilities": {"commande": 0.7, "reclamation": 0.3}}, "angry": {"type": "noul", "noul": 0.1}}
    jev, seen = fake_jev(answers)
    res = await jev.ask("je voudrais commander", {"intent": choice_question(None, ["commande", "reclamation"]), "angry": yes_no_question("Le client est fâché.")})
    assert res["answers"] == answers and res["usage"]["input_tokens"] == 42
    assert set(sent(seen)["questions"]) == {"intent", "angry"}


async def test_http_error_is_a_provider_error():
    jev, _ = fake_jev(status=401, body='{"detail":"Invalid API key"}')
    with pytest.raises(ProviderError, match=r"jev HTTP 401.*clé API refusée"):
        await jev.yes_no("x", "y")


def test_factory_none_without_key():
    assert make_jev_client(JevSettings(api_key="", base_url="https://api.typesafe.ai", model="jev-latest")) is None
    jev = make_jev_client(JevSettings(api_key="k", base_url="https://api.typesafe.ai", model="jev-latest"))
    assert isinstance(jev, JevClient) and jev.model == "jev-latest"


async def test_example_pick_product_and_is_yes():
    hits = [{"type": "product", "id": "prd_1", "label": "Bar d'élevage", "sublabel": "Grèce"}, {"type": "product", "id": "prd_2", "label": "Bar de ligne"}]
    jev, seen = fake_jev({"q": {"type": "choice", "choice": "prd_2", "confidence": 0.9, "probabilities": {"prd_1": 0.1, "prd_2": 0.9}}})
    assert await pick_product(jev, "du bar de ligne", hits) == "prd_2"
    assert sent(seen)["questions"]["q"]["criteria"] == {"prd_1": "Bar d'élevage — Grèce", "prd_2": "Bar de ligne"}

    jev, _ = fake_jev({"q": {"type": "choice", "choice": "prd_2", "confidence": 0.52, "probabilities": {"prd_1": 0.48, "prd_2": 0.52}}})
    assert await pick_product(jev, "du bar", hits) is None  # too close: let the LLM ask

    jev, seen = fake_jev({"q": {"type": "noul", "noul": 0.5}})
    assert await pick_product(jev, "x", hits[:1]) == "prd_1" and not seen  # one candidate: no call
    assert await is_yes(jev, "Je vous mets 5 kg ?", "euh") is None
