"""/api/suppliers: list, detail, usual basket, history, edit."""

from fastapi import APIRouter, Query

from app.core.listing import ListDep, Page
from app.dependencies import CtxDep, data
from app.schemas.domain import Supplier, SupplierEvent
from app.schemas.inputs import SupplierEventInput, SupplierPatch
from app.schemas.views import SupplierDetail, SupplierEventSummary, UsualBasketLine
from app.services import catalog, purchasing, supplier_events, tags

router = APIRouter(prefix="/api/suppliers", tags=["suppliers"])


@router.get("", response_model=list[Supplier] | Page[Supplier])
async def list_suppliers(
    lq: ListDep,
    tag: str | None = None,
    q: str | None = Query(None, description="Name, city or contact"),
    category: str | None = Query(None, description="A product category the supplier sells"),
):
    """By name. sort: name | city | tags | lead | terms | min."""
    return catalog.list_suppliers(lq, tag=tag or None, q=q or None, category=category or None)


@router.patch("/{id}", response_model=Supplier)
async def update_supplier(id: str, ctx: CtxDep, body: SupplierPatch | None = None):
    return tags.update_supplier(ctx, id, data(body))


@router.get("/{id}", response_model=SupplierDetail)
async def get_supplier(id: str):
    return catalog.supplier_detail(id)


@router.get("/{id}/usual", response_model=list[UsualBasketLine])
async def supplier_usual(id: str):
    """What we usually buy from this supplier (last 60 days)."""
    return purchasing.supplier_usual_basket(id)


@router.get("/{id}/events", response_model=list[SupplierEventSummary] | Page[SupplierEventSummary])
async def supplier_history(
    id: str,
    lq: ListDep,
    type: str | None = Query(None, description="Comma list of event types"),
    status: str | None = Query(None, description="open | resolved"),
    q: str | None = None,
):
    """Newest first. sort: at | type | status | amount | open (open issues first, then newest)."""
    return supplier_events.list_supplier_events(lq, id, type=type or None, status=status or None, q=q or None)


@router.post("/{id}/events", response_model=SupplierEvent, status_code=201)
async def add_supplier_event(id: str, body: SupplierEventInput, ctx: CtxDep):
    return supplier_events.create_supplier_event(ctx, id, body.data())
