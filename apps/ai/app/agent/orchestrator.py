"""
OWNER: Youssef (T4 finished by Amine Khalil, 24/11) · switch TEAM_ORCHESTRATOR · contract: docs/team/interfaces.md §3

Several agents at once, to answer in < 1.5 s (advice of Stockline's CTO).

Real life: Lucie keeps talking to the caller ("Oui Nadine, je regarde…") while a colleague checks the stock.

    caller's words
       │
       ├──► SPEAKER: says « je regarde » + keyboard at 0 s           services/fillers.py (TEAM_FILLERS=4)
       │
       ├──► COLLEAGUE (this file): checks the ERP for every product the caller named, IN PARALLEL
       │        (stock + this client's price + promo + substitutes, tools/insight.py), deterministic, no model
       │
       └──► BRAIN (LLM_MODEL, Sonnet, full prompt + tools) = run_agent, which starts with the colleague's result
                in hand: a stock / price question is answered in ONE model call instead of two
            simple turns (« c'est bon, validez », « merci ») go to the FAST model alone: agent/router.py
            (TEAM_ROUTER), picked by the voice session before calling us

Rules kept from the plan: the fast side never states a number, a stock or a price (only canned phrases and the
brain do); nothing is ever written by the colleague (reads only); bounded by PREFETCH_BUDGET so a slow ERP never
delays the brain much; an order with quantities is left to place_order (already ONE tool call), so the colleague
does not slow it down.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from collections.abc import AsyncIterator
from functools import lru_cache

from app import team_flags
from app.clients import LLMClient
from app.schemas import ChatMessage, ChatMode, ChatStreamEvent
from app.tools import Tool

from .call_context import CallContext
from .loop import run_agent

log = logging.getLogger(__name__)

PREFETCH_BUDGET = 0.8  # seconds: past this the brain starts without the colleague's result
MAX_PRODUCTS = 3

# A question about a product (stock, price, availability), not an order: « vous avez encore du tourage AOP ? »
QUESTION = re.compile(
    r"\?|\b(?:vous avez|vous auriez|il (?:vous )?reste|il y a|y a-t-il|en stock|dispo|disponible|rupture|"
    r"combien|quel prix|le prix|c'est combien|ça coûte|ca coute|vous le faites|vous les faites|tarif)\b",
    re.I,
)
# A quantity said with the product: an order → place_order does it in one call
QUANTITY = re.compile(
    r"\b(?:\d+|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|onze|douze|treize|quatorze|quinze|seize|vingt|"
    r"trente|quarante|cinquante|soixante|cent|demi|demie|douzaine)\b",
    re.I,
)


def _key(s: str) -> str:
    from .rules_order import _ARTICLES, _norm, _singular

    s = re.sub(r"[^\w'\- ]", " ", _norm(s))
    return _singular(_ARTICLES.sub("", re.sub(r"\s+", " ", s).strip()))


def products_in(text: str, products: dict[str, dict], usual_ids: set[str] | None = None) -> list[str]:
    """
    « vous avez encore du tourage AOP et de la levure ? » → [prd_0025, prd_0011]: the products named, longest name
    first, catalogue aliases and names (before the parenthesis), plural and accents ignored. A shared or ambiguous word
    (« tourage », « farine ») counts only when exactly one product of the client's usual basket has it.
    """
    from .rules_order import AMBIGUOUS_WORDS

    usual_ids = usual_ids or set()
    index: dict[str, set[str]] = {}
    for pid, p in products.items():
        if not p.get("active", True):
            continue
        for name in [*(p.get("aliases") or []), p.get("name", "").split(" (")[0]]:
            k = _key(name)
            if len(k) >= 3:
                index.setdefault(k, set()).add(pid)
    said = f" {_key(text)} "
    found: list[str] = []
    for k in sorted(index, key=len, reverse=True):
        if f" {k} " not in said:
            continue
        pids = index[k]
        if k in AMBIGUOUS_WORDS or len(pids) > 1:
            pids = pids & usual_ids
        if len(pids) == 1:
            pid = next(iter(pids))
            if pid not in found:
                found.append(pid)
        said = said.replace(f" {k} ", " " * (len(k) + 2))  # these words are used: « tourage AOP » ≠ « tourage »
        if len(found) >= MAX_PRODUCTS:
            break
    return found


def wants_prefetch(heard: str) -> bool:
    """A question about products (stock, price) → yes. An order with quantities → no (place_order: one call)."""
    from .router import is_simple_turn

    if not heard or is_simple_turn(heard):
        return False
    return bool(QUESTION.search(heard)) or not QUANTITY.search(heard)


def _brief(insight: dict) -> dict:
    """What the brain needs to answer, small (every byte is read by the model)."""
    p = insight.get("product") or {}
    keep = ("id", "name", "unit", "available", "clientPrice", "promo", "incoming", "betterPriceWithVolume")
    out = {"product": {k: p[k] for k in keep if p.get(k) is not None}, "inStock": insight.get("inStock")}
    for k in ("missing", "substitution"):
        if insight.get(k) is not None:
            out[k] = insight[k]
    if alts := insight.get("alternatives"):
        out["alternatives"] = [
            {k: a[k] for k in ("id", "name", "unit", "available", "clientPrice", "promo") if a.get(k) is not None}
            for a in alts[:2]
        ]
    return out


def _eligible(call_context: CallContext | None) -> bool:
    return call_context is not None and not call_context.blocked and not call_context.is_new


async def spot(heard: str, call_context: CallContext, actor_name: str | None = None) -> tuple[str, ...]:
    """The products named in `heard` (catalogue cached 10 min: no ERP call after the first)."""
    from app.tools.erp import ErpClient
    from app.tools.order_review import products_by_id
    from app.tools.registry import ToolContext

    catalogue = await products_by_id(ToolContext(erp=ErpClient("voice_agent", actor_name), actor="voice_agent"))
    return tuple(products_in(heard, catalogue, {u.product_id for u in call_context.usual}))


async def facts_for(pids: tuple[str, ...], call_context: CallContext, actor_name: str | None = None) -> list[dict]:
    """Stock + this client's price + promo + substitutes of these products, in parallel (reads only)."""
    from app.tools.erp import ErpClient
    from app.tools.insight import gather_insight

    erp = ErpClient("voice_agent", actor_name)
    results = await asyncio.gather(*(gather_insight(erp, call_context.client_id, pid, None) for pid in pids),
                                   return_exceptions=True)
    return [_brief(r) for r in results if isinstance(r, dict)]


class Anticipation:
    """
    The colleague starts while the caller is still speaking: every partial transcript is scanned for products (no
    model, catalogue cached) and, as soon as the products named change, their ERP facts are fetched in the background.
    At the end of the sentence the final transcript is scanned again: same products → the facts are (usually) already
    there and the brain starts at once; otherwise the speculative fetch is dropped and the normal check runs.
    """

    def __init__(self, call_context: CallContext | None, actor_name: str | None = None):
        self.cc, self.actor = call_context, actor_name
        self.pids: tuple[str, ...] = ()
        self.task: asyncio.Task | None = None  # the facts for self.pids
        self._latest: str | None = None
        self._spotting: asyncio.Task | None = None

    def heard(self, partial: str) -> None:
        """Called on every partial transcript; never blocks the transcription."""
        if not team_flags.orchestrator() or not _eligible(self.cc) or not partial.strip():
            return
        self._latest = partial
        if self._spotting is None or self._spotting.done():
            self._spotting = asyncio.create_task(self._spot_latest())

    async def _spot_latest(self) -> None:
        while self._latest is not None:
            text, self._latest = self._latest, None
            try:
                pids = await spot(text, self.cc, self.actor)
            except Exception:
                return
            if pids and pids != self.pids:
                if self.task:
                    self.task.cancel()
                self.pids = pids
                self.task = asyncio.create_task(facts_for(pids, self.cc, self.actor))

    def take(self, pids: tuple[str, ...]) -> asyncio.Task | None:
        """The speculative fetch if it was for exactly these products, else None (and it is dropped)."""
        if self.task and pids == self.pids:
            return self.task
        self.cancel()
        return None

    def cancel(self) -> None:
        for t in (self._spotting, self.task):
            if t and not t.done():
                t.cancel()


async def colleague_check(heard: str, call_context: CallContext | None, actor_name: str | None = None,
                          anticipated: Anticipation | None = None) -> list[dict]:
    """The ERP facts about the products the caller named, fetched in parallel. [] when nothing to check."""
    if not _eligible(call_context) or not wants_prefetch(heard):
        if anticipated:
            anticipated.cancel()
        return []
    pids = await spot(heard, call_context, actor_name)
    if not pids:
        return []
    if anticipated and (task := anticipated.take(pids)):
        early = task.done()
        try:
            facts = await task
            print(f"[orchestrateur] vérification anticipée {'déjà prête' if early else 'en cours'} à la fin de la phrase", flush=True)
            return facts
        except Exception:
            pass
    return await facts_for(pids, call_context, actor_name)


def with_colleague_note(message: ChatMessage, facts: list[dict]) -> ChatMessage:
    note = (
        "\n\n[Vérifié dans l'ERP pendant que le client parlait (stock, prix de CE client, promo, remplaçants classés) ; "
        "réponds avec ces faits sans rappeler product_insight pour ces produits ; une quantité demandée se compare à "
        "« available » : "
        + json.dumps(facts, ensure_ascii=False, separators=(",", ":"))
        + "]"
    )
    return message.model_copy(update={"content": (message.content or "") + note})


async def run_voice_turn(
    messages: list[ChatMessage],
    *,
    llm: LLMClient,
    tools: list[Tool],
    mode: ChatMode = "voice",
    actor_name: str | None = None,
    call_context: CallContext | None = None,
    anticipated: Anticipation | None = None,  # started while the caller was still speaking (voice_session)
) -> AsyncIterator[ChatStreamEvent]:
    """Same contract as run_agent (same events, appends to `messages`). The voice session calls this."""
    asked_at, asked = len(messages) - 1, messages[-1] if messages else None
    if team_flags.orchestrator() and messages and messages[-1].role == "user":
        started = time.perf_counter()
        try:
            facts = await asyncio.wait_for(
                colleague_check(messages[-1].content or "", call_context, actor_name, anticipated), PREFETCH_BUDGET
            )
        except Exception as exc:  # slow or failing ERP: the brain does it itself, as before
            print(f"[orchestrateur] vérification sautée ({type(exc).__name__})", flush=True)
            facts = []
        if facts:
            messages[-1] = with_colleague_note(messages[-1], facts)
            names = ", ".join(f["product"].get("name", "?") for f in facts)
            print(f"[orchestrateur] vérifié en parallèle en {int((time.perf_counter() - started) * 1000)} ms : {names}", flush=True)

    try:
        async for ev in run_agent(messages, llm=llm, tools=tools, mode=mode, actor_name=actor_name, call_context=call_context):
            yield ev
    finally:
        # The note served this turn only: the history keeps the caller's words (measured: kept notes slowed the
        # next turns by 1.2-1.5 s, the model kept reasoning about products already answered).
        if asked is not None and 0 <= asked_at < len(messages) and messages[asked_at] is not asked:
            messages[asked_at] = asked


@lru_cache(maxsize=1)
def get_fast_llm_client() -> LLMClient:
    """A second LLM client, same provider and key as LLM_*, on the fast model (TEAM_FAST_MODEL)."""
    from dataclasses import replace

    from app.clients.factory import make_llm_client
    from app.config import settings

    return make_llm_client(replace(settings.llm, model=team_flags.fast_model()))
