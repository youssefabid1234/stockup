"""T4 orchestrator: the "colleague" checks the ERP in parallel for the products the caller named."""

import asyncio

import pytest

from app.agent import orchestrator as orch
from app.agent.call_context import CallContext, UsualItem
from app.schemas import ChatMessage

CATALOGUE = {
    "prd_0001": {"id": "prd_0001", "name": "Farine de blé T55 tradition française (sac 25 kg)", "aliases": ["tradi", "T55 tradi"]},
    "prd_0002": {"id": "prd_0002", "name": "Farine de seigle T130 (sac 25 kg)", "aliases": ["seigle"]},
    "prd_0011": {"id": "prd_0011", "name": "Levure fraîche boulangère (pain 500 g)", "aliases": ["levure", "pains de levure"]},
    "prd_0025": {"id": "prd_0025", "name": "Beurre de tourage AOP (plaque 2 kg)", "aliases": ["tourage AOP", "tourage"]},
    "prd_0026": {"id": "prd_0026", "name": "Beurre de tourage 82 % (plaque 2 kg)", "aliases": ["tourage 82", "tourage"]},
}


def test_products_named_longest_first_and_ambiguous_words():
    assert orch.products_in("Vous avez encore du tourage AOP et de la levure ?", CATALOGUE) == ["prd_0025", "prd_0011"]
    assert orch.products_in("il vous reste des pains de levure ?", CATALOGUE) == ["prd_0011"]
    # « tourage » alone: two products → only the one of the client's usual basket
    assert orch.products_in("vous avez du tourage ?", CATALOGUE) == []
    assert orch.products_in("vous avez du tourage ?", CATALOGUE, {"prd_0026"}) == ["prd_0026"]
    assert orch.products_in("Bonjour, c'est Nadine.", CATALOGUE) == []


def test_only_questions_and_orders_without_quantity_are_prefetched():
    assert orch.wants_prefetch("Vous avez encore du tourage AOP ?")
    assert orch.wants_prefetch("C'est combien la tradi en ce moment")
    assert orch.wants_prefetch("Je voudrais de la tradi pour jeudi")  # no quantity yet: the brain will ask
    assert not orch.wants_prefetch("Mettez-moi dix sacs de tradi pour jeudi")  # place_order: one call already
    assert not orch.wants_prefetch("C'est bon, validez.")
    assert not orch.wants_prefetch("")


def test_brief_keeps_what_the_brain_needs():
    insight = {"product": {"id": "prd_0025", "name": "Tourage AOP", "unit": "kg", "available": 0, "clientPrice": 11.4,
                           "listPrice": 11.4, "priceExplanation": "long text"},
               "inStock": False, "substitution": "accepte",
               "alternatives": [{"id": "prd_0026", "name": "82 %", "unit": "kg", "available": 120, "clientPrice": 8.46,
                                 "promo": "-8 %", "listPrice": 9.2}, {"id": "a2"}, {"id": "a3"}]}
    b = orch._brief(insight)
    assert "priceExplanation" not in b["product"] and b["substitution"] == "accepte"
    assert len(b["alternatives"]) == 2 and b["alternatives"][0]["promo"] == "-8 %" and "listPrice" not in b["alternatives"][0]


def _ctx(**kw):
    return CallContext(client_id="cli_0001", name="Maison Sarrailh",
                       usual=[UsualItem(product_id="prd_0026", product_name="82", unit="kg")], **kw)


async def _collect(gen):
    return [ev async for ev in gen]


@pytest.fixture
def fake_brain(monkeypatch):
    seen = {}

    async def run_agent(messages, **kw):
        seen["last"] = messages[-1].content
        seen["call_context"] = kw.get("call_context")
        yield "done"

    monkeypatch.setattr(orch, "run_agent", run_agent)
    return seen


def test_switch_off_is_the_kit(monkeypatch, fake_brain):
    monkeypatch.delenv("TEAM_ORCHESTRATOR", raising=False)
    called = []
    monkeypatch.setattr(orch, "colleague_check", lambda *a, **k: called.append(1))
    msgs = [ChatMessage(role="user", content="Vous avez du tourage AOP ?")]
    assert asyncio.run(_collect(orch.run_voice_turn(msgs, llm=None, tools=[], call_context=_ctx()))) == ["done"]
    assert not called and fake_brain["last"] == "Vous avez du tourage AOP ?"


def test_switch_on_gives_the_facts_to_the_brain(monkeypatch, fake_brain):
    monkeypatch.setenv("TEAM_ORCHESTRATOR", "1")

    async def colleague(heard, cc, actor_name=None):
        return [{"product": {"id": "prd_0025", "name": "Beurre de tourage AOP", "available": 0}, "inStock": False}]

    monkeypatch.setattr(orch, "colleague_check", colleague)
    msgs = [ChatMessage(role="user", content="Vous avez du tourage AOP ?")]
    asyncio.run(_collect(orch.run_voice_turn(msgs, llm=None, tools=[], call_context=_ctx())))
    assert fake_brain["last"].startswith("Vous avez du tourage AOP ?\n\n[Vérifié dans l'ERP")
    assert '"id":"prd_0025"' in fake_brain["last"]
    assert msgs[-1].content == "Vous avez du tourage AOP ?"  # the note served this turn only: not kept in the history


def test_slow_or_failing_erp_never_blocks_the_brain(monkeypatch, fake_brain):
    monkeypatch.setenv("TEAM_ORCHESTRATOR", "1")
    monkeypatch.setattr(orch, "PREFETCH_BUDGET", 0.05)

    async def slow(*a, **k):
        await asyncio.sleep(1)
        return [{"product": {}}]

    monkeypatch.setattr(orch, "colleague_check", slow)
    msgs = [ChatMessage(role="user", content="Vous avez du tourage AOP ?")]
    assert asyncio.run(_collect(orch.run_voice_turn(msgs, llm=None, tools=[], call_context=_ctx()))) == ["done"]
    assert fake_brain["last"] == "Vous avez du tourage AOP ?"

    async def broken(*a, **k):
        raise RuntimeError("ERP down")

    monkeypatch.setattr(orch, "colleague_check", broken)
    assert asyncio.run(_collect(orch.run_voice_turn(msgs, llm=None, tools=[], call_context=_ctx()))) == ["done"]


def test_blocked_or_unknown_caller_is_not_checked():
    assert asyncio.run(orch.colleague_check("Vous avez du tourage AOP ?", None)) == []
    assert asyncio.run(orch.colleague_check("Vous avez du tourage AOP ?", _ctx(status="blocked"))) == []
