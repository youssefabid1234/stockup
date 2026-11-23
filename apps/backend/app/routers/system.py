"""/api: health, meta, dashboard, global search, activity log (+ live SSE stream), admin reset."""

import asyncio
import json
import logging

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from app.core.activity import bus, list_events
from app.core.config import DATA_DIR
from app.core.datapack import counts, reset_from_pack
from app.core.db import get_meta
from app.core.listing import LIMIT_MAX, ListDep, Page, legacy_limit
from app.core.utils import int_param
from app.schemas.domain import ActivityEvent, Category, Meta
from app.services.categories import list_categories
from app.schemas.views import Dashboard, Health, Ok, SearchResult
from app.services.dashboard import dashboard
from app.services.search import search

router = APIRouter(prefix="/api", tags=["system"])
log = logging.getLogger("api")


@router.get("/health", response_model=Health)
async def health():
    return {"ok": True, "today": get_meta()["today"]}


@router.get("/meta", response_model=Meta)
async def meta():
    """meta.json + the company's trade and region (DATA_DIR/stats.json, written by the data generator)."""
    out = dict(get_meta())
    out.setdefault("categories", list_categories())
    stats = DATA_DIR / "stats.json"
    if stats.exists():
        try:
            s = json.loads(stats.read_text())
            out.setdefault("trade", s.get("trade"))
            out.setdefault("region", s.get("region"))
        except (OSError, ValueError):
            pass
    return out


@router.get("/categories", response_model=list[Category])
async def categories():
    """Product categories of the company (per data pack), with French labels."""
    return list_categories()


@router.get("/dashboard", response_model=Dashboard)
async def get_dashboard():
    return dashboard()


@router.get("/search", response_model=list[SearchResult])
async def global_search(
    q: str = "",
    types: str | None = Query(None, description="Comma list of client,product,supplier,order (+ context, opt-in)"),
    limit: str | None = None,
):
    """Fuzzy, accent-insensitive search; uses product aliases and drops spoken French fillers."""
    return search(q, [t for t in (types or "").split(",") if t], min(int_param(limit, 20), LIMIT_MAX))


@router.get("/events", response_model=list[ActivityEvent] | Page[ActivityEvent])
async def activity_events(
    lq: ListDep,
    actor: str | None = Query(None, description="user | ai (assistant + voice agent) | comma list of actors"),
    entity: str | None = Query(None, description="Comma list of entity types (order, client…)"),
):
    """Activity log, newest first (default limit 50). Envelope extras: counts {ai, user} (ignoring `actor`)."""
    lq = legacy_limit(lq, 50)
    rows, total, counts = list_events(lq.limit, lq.offset, actor or None, entity or None)
    return {"items": rows, "total": total, "limit": lq.limit, "offset": lq.offset, "counts": counts} if lq.envelope else rows


@router.get(
    "/events/stream",
    response_class=StreamingResponse,
    responses={200: {"content": {"text/event-stream": {}}, "description": "One `event: activity` per ActivityEvent"}},
)
async def activity_stream():
    """Server-Sent Events: `ready` once, then one `activity` event per write, `ping` every 15 s."""

    async def stream():
        queue = bus.subscribe()
        try:
            yield "event: ready\ndata: {}\n\n"
            while True:
                try:
                    ev = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield "event: ping\ndata: \n\n"
                    continue
                data = json.dumps(ev, ensure_ascii=False, separators=(",", ":"))
                yield f"event: activity\nid: {ev['id']}\ndata: {data}\n\n"
        finally:
            bus.unsubscribe(queue)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@router.post("/admin/reset", response_model=Ok)
async def admin_reset():
    """Wipe the database and reload the data pack from DATA_DIR."""
    source = reset_from_pack()
    log.info("reset from %s: %s", source, counts())
    return {"ok": True}
