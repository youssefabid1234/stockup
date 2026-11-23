"""/api/supplier-events: supplier history across all suppliers."""

from fastapi import APIRouter, Query

from app.core.listing import ListDep, Page
from app.dependencies import CtxDep, data, iso_date_query
from app.schemas.domain import SupplierEvent
from app.schemas.inputs import SupplierEventPatch
from app.schemas.views import SupplierEventSummary
from app.services import supplier_events

router = APIRouter(prefix="/api/supplier-events", tags=["suppliers"])


@router.get("", response_model=list[SupplierEventSummary] | Page[SupplierEventSummary])
async def search_supplier_events(
    lq: ListDep,
    type: str | None = Query(None, description="Comma list of event types"),
    status: str | None = Query(None, description="open | resolved"),
    supplier_id: str | None = Query(None, alias="supplierId"),
    q: str | None = None,
    date_from: str | None = Query(None, alias="from"),
    date_to: str | None = Query(None, alias="to"),
):
    """Newest first. sort: at | type | status | amount | open (open issues first).
    Envelope extras: counts (per status, ignoring `status`), countsByType, sums.amount."""
    return supplier_events.search_supplier_events(
        lq, supplier_id or None, type=type or None, status=status or None, q=q or None,
        date_from=iso_date_query(date_from), date_to=iso_date_query(date_to),
    )  # fmt: skip


@router.patch("/{id}", response_model=SupplierEvent)
async def update_supplier_event(id: str, ctx: CtxDep, body: SupplierEventPatch | None = None):
    return supplier_events.update_supplier_event(ctx, id, data(body))
