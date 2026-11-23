"""
Jev, TypeSafe AI's decision model (POST https://api.typesafe.ai/v1/systemone). Not an LLM: it writes no text.

You send a `state` (the content: a string or any JSON) and named, typed `questions`; it answers each one with
probabilities, in a few hundred ms (168–752 ms measured). Good for the small decisions around the LLM: routing, "which product did the
caller mean", "is that a yes?", "how urgent is it?".

    question type  you send                                    you get back
    choice         criteria {name: description | None}         choice, confidence, probabilities {name: p}
    score          criteria [level 0, level 1, …] (ordered)    score (expected level, may be 2.4), confidence, probabilities
    noul           instructions (+ criteria {true, false})     noul = probability of yes / true, 0..1
    box            instructions, on an image asset             box {top, bottom, left, right} (not wrapped here: use ask())

Schema: https://api.typesafe.ai/openapi.json (the official `typesafe-sdk` is generated from it). Raw httpx here,
like the other clients: the call is one small JSON POST, and every field is visible.
"""

from dataclasses import dataclass
from typing import Any

import httpx

from .http import check_ok, http_client

Content = str | dict[str, Any] | list[Any]  # what `state`, instructions and criteria accept


@dataclass(frozen=True)
class Choice:
    choice: str  # the option with the highest probability
    confidence: float  # 0..1: below ~0.6, ask the caller instead of guessing
    probabilities: dict[str, float]  # every option → p (sums to ~1)


@dataclass(frozen=True)
class Score:
    score: float  # probability-weighted level, e.g. 1.7 between level 1 and level 2
    confidence: float
    probabilities: dict[str, float]  # "0", "1", … → p


# ── Question builders (plain dicts, exactly the wire format) ──


def choice_question(instructions: Content | None, options: dict[str, Content | None] | list[str]) -> dict:
    """Pick one option. `options`: names, or {name: when it applies} (a description helps on vague names)."""
    criteria = dict.fromkeys(options) if isinstance(options, list) else dict(options)
    return _question("choice", instructions, criteria)


def score_question(instructions: Content | None, levels: list[Content]) -> dict:
    """Rate on ordered levels: levels[0] scores 0, levels[1] scores 1, …"""
    return _question("score", instructions, list(levels))


def yes_no_question(instructions: Content | None, yes: Content | None = None, no: Content | None = None) -> dict:
    """A yes/no question or a statement to check ("noul"). `yes` / `no` say what counts as each answer."""
    return _question("noul", instructions, {"true": yes, "false": no} if yes is not None or no is not None else None)


def _question(kind: str, instructions: Content | None, criteria: Any) -> dict:
    q: dict[str, Any] = {"type": kind}
    if instructions is not None:
        q["instructions"] = instructions
    if criteria is not None:
        q["criteria"] = criteria
    return q


class JevClient:
    provider = "jev"

    def __init__(
        self,
        api_key: str,
        model: str = "jev-latest",
        base_url: str = "https://api.typesafe.ai",
        http: httpx.AsyncClient | None = None,
        timeout: float = 10.0,  # a decision is fast; don't let one hang a voice turn
    ):
        self.api_key, self.model, self.base_url, self.http, self.timeout = api_key, model, base_url.rstrip("/"), http, timeout

    async def ask(self, state: Content, questions: dict[str, dict]) -> dict:
        """The raw call: several named questions about one state, in one request.
        Returns the response JSON: {"model", "answers": {name: {"type", …}}, "usage": {"input_tokens", "output_tokens"}}."""
        if not questions:
            raise ValueError("Jev needs at least one question")
        res = await (self.http or http_client()).post(
            f"{self.base_url}/v1/systemone",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={"model": self.model, "state": state, "questions": questions},
            timeout=self.timeout,
        )
        await check_ok(res, "jev")
        return res.json()

    async def choose(self, state: Content, question: Content | None, options: dict[str, Content | None] | list[str]) -> Choice:
        """Which option fits the state? e.g. choose(utterance, "Quel produit ?", {"prd_1": "Bar de ligne 1-2 kg", …})."""
        a = (await self.ask(state, {"q": choice_question(question, options)}))["answers"]["q"]
        return Choice(a["choice"], a["confidence"], a["probabilities"])

    async def score(self, state: Content, question: Content | None, levels: list[Content]) -> Score:
        """Where does the state sit on these ordered levels? e.g. urgency: ["peut attendre", "aujourd'hui", "tout de suite"]."""
        a = (await self.ask(state, {"q": score_question(question, levels)}))["answers"]["q"]
        return Score(a["score"], a["confidence"], a["probabilities"])

    async def yes_no(self, state: Content, question: Content | None, yes: Content | None = None, no: Content | None = None) -> float:
        """Probability (0..1) that the answer is yes / the statement is true. Near 0.5 = unsure: ask again."""
        a = (await self.ask(state, {"q": yes_no_question(question, yes, no)}))["answers"]["q"]
        return a["noul"]
