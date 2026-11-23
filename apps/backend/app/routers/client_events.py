"""/api/client-events: client history across all clients."""

from fastapi import APIRouter, Query

from app.core.listing import ListDep, Page
from app.dependencies import CtxDep, data, iso_date_query
from app.schemas.domain import ClientEvent
from app.schemas.inputs import ClientEventPatch
from app.schemas.views import ClientEventSummary
from app.services import client_events

router = APIRouter(prefix="/api/client-events", tags=["clients"])


@router.get("", response_model=list[ClientEventSummary] | Page[ClientEventSummary])
async def search_client_events(
    lq: ListDep,
    type: str | None = Query(None, description="Comma list of event types"),
    status: str | None = Query(None, description="open | resolved"),
    client_id: str | None = Query(None, alias="clientId"),
    q: str | None = Query(None, description="Every word in title + description, accent-insensitive"),
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
):
    """Newest first. sort: at | type | status | amount | open (open issues first).
    Envelope extras: counts (per status, ignoring `status`), countsByType, sums.amount."""
    return client_events.search_client_events(
        lq, client_id or None, type=type or None, status=status or None, q=q or None,
        date_from=iso_date_query(date_from), date_to=iso_date_query(date_to),
    )  # fmt: skip


@router.patch("/{id}", response_model=ClientEvent)
async def update_client_event(id: str, ctx: CtxDep, body: ClientEventPatch | None = None):
    """Resolving (status → resolved) sets resolvedAt."""
    return client_events.update_client_event(ctx, id, data(body))
