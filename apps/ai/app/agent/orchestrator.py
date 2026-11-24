"""
OWNER: Youssef · switch TEAM_ORCHESTRATOR · contract: docs/team/interfaces.md §3

Several agents at once, to answer in < 1.5 s (advice of Stockline's CTO).

Real life: Lucie keeps talking to the caller ("Oui Nadine, je regarde…") while a colleague checks the stock.

    caller's words
       │
       ├──► FAST "speaker" agent (TEAM_FAST_MODEL, Haiku, tiny prompt, no tools)
       │        says right away what can be said without the ERP (greeting, "c'est noté", a question back)
       │
       └──► BRAIN agent (LLM_MODEL, Sonnet, full prompt + tools) = today's run_agent
                checks, decides, acts in the ERP, gives the real answer

v0 (now): run_voice_turn() just delegates to run_agent → exactly the kit's behaviour. The switch is OFF.

TODO(Youssef), in order:
  1. get_fast_llm_client(): a second LLM client on TEAM_FAST_MODEL (done below, untested)
  2. route easy turns (yes / no / thanks / "c'est tout") to the fast agent alone; Jev can classify the turn
     (clients/jev.py, examples in agent/jev_examples.py)
  3. hard turns: start the fast agent's acknowledgement AND the brain in parallel; never let them contradict
     (the fast agent never states a number, a stock, a price or a promise — only the brain does)
  4. preload: when the brain calls get_client (or search returns a single client), load the CallContext
     (agent/call_context.py) for the next turns; speculative: start it on the partial transcript
  5. measure each change with scripts/run_scenarios.py and write the numbers in DECISIONS.md
Interface with Mohamed Amine (fillers): the voice session asks fillers.on_turn_start() before calling us; if
the fast agent already speaks, the filler must not overlap (see interfaces.md §3).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from app import team_flags
from app.clients import LLMClient
from app.schemas import ChatMessage, ChatMode, ChatStreamEvent
from app.tools import Tool

from .call_context import CallContext
from .loop import run_agent


async def run_voice_turn(
    messages: list[ChatMessage],
    *,
    llm: LLMClient,
    tools: list[Tool],
    mode: ChatMode = "voice",
    actor_name: str | None = None,
    call_context: CallContext | None = None,
) -> AsyncIterator[ChatStreamEvent]:
    """Same contract as run_agent (same events, appends to `messages`). The voice session calls this."""
    if not team_flags.orchestrator():
        async for ev in run_agent(messages, llm=llm, tools=tools, mode=mode, actor_name=actor_name, call_context=call_context):
            yield ev
        return

    # TODO(Youssef): fast agent + brain in parallel. Until then, same as the kit.
    async for ev in run_agent(messages, llm=llm, tools=tools, mode=mode, actor_name=actor_name, call_context=call_context):
        yield ev


@lru_cache(maxsize=1)
def get_fast_llm_client() -> LLMClient:
    """A second LLM client, same provider and key as LLM_*, on the fast model (TEAM_FAST_MODEL)."""
    from dataclasses import replace

    from app.clients.factory import make_llm_client
    from app.config import settings

    return make_llm_client(replace(settings.llm, model=team_flags.fast_model()))
