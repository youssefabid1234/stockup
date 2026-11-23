"""Who did what: the request actor, the anchored business clock, and the activity log + live bus.

Every write appends one ActivityEvent (`log_event`). Once the surrounding transaction commits,
it is pushed to every open SSE connection (GET /api/events/stream).
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app import crud
from app.core.db import Doc, get_meta, on_commit

Actor = Literal["user", "ai_chat", "voice_agent", "system"]


@dataclass(frozen=True)
class Ctx:
    """Passed to every write: who is acting (from the x-actor / x-actor-name headers)."""

    actor: Actor = "user"
    actor_name: str | None = None


SYSTEM_CTX = Ctx(actor="system")

# ───────── Clock ─────────


def today() -> str:
    """The dataset is anchored on a fixed date (meta.today). Use it instead of date.today()."""
    return get_meta()["today"]


def now() -> str:
    """Timestamp on the anchored day with the real wall-clock time, so new records land "today"."""
    t = datetime.now(timezone.utc)
    return f"{today()}T{t:%H:%M:%S}.{t.microsecond // 1000:03d}Z"


# ───────── Live bus (SSE) ─────────


class EventBus:
    """Fan-out of activity events to every SSE subscriber (one asyncio.Queue each)."""

    def __init__(self) -> None:
        self.subscribers: set[asyncio.Queue[Doc]] = set()

    def subscribe(self) -> asyncio.Queue[Doc]:
        q: asyncio.Queue[Doc] = asyncio.Queue()
        self.subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Doc]) -> None:
        self.subscribers.discard(q)

    def publish(self, event: Doc) -> None:
        for q in self.subscribers:
            q.put_nowait(event)


bus = EventBus()

# ───────── Activity log ─────────


def log_event(ctx: Ctx, type: str, entity: str, entity_id: str, summary: str) -> Doc:
    """Append one ActivityEvent; it is broadcast only once the transaction commits."""
    ev: Doc = {
        "id": crud.events.next_id("evt_", 7),
        "at": now(),
        "actor": ctx.actor,
        **({"actorName": ctx.actor_name} if ctx.actor_name else {}),
        "type": type,
        "entity": entity,
        "entityId": entity_id,
        "summary": summary,
    }
    crud.events.put(ev)
    on_commit(lambda: bus.publish(ev))
    return ev


def list_events(limit: int = 50, offset: int = 0, actor: str | None = None, entity: str | None = None) -> tuple[list[Doc], int, Doc]:
    """Newest first: (page, total matching, counts). actor: ai (ai_chat + voice_agent) | a comma list (user,system…);
    entity: comma list. counts = {"ai": n, "user": n} (agents vs everyone else), ignoring `actor`."""
    actors = {"ai_chat", "voice_agent"} if actor == "ai" else set(actor.split(",")) if actor else None
    entities = set(entity.split(",")) if entity else None
    base = [e for e in reversed(crud.events.all()) if not entities or e["entity"] in entities]
    rows = [e for e in base if e["actor"] in actors] if actors else base
    ai = sum(1 for e in base if e["actor"] in ("ai_chat", "voice_agent"))
    return rows[offset : offset + limit], len(rows), {"ai": ai, "user": len(base) - ai}
