"""/api/purchase-orders: supplier orders (draft → sent → partially_received → received)."""

from fastapi import APIRouter, Query

from app.core.listing import ListDep, Page
from app.dependencies import CtxDep, data
from app.schemas.inputs import PurchaseOrderInput, PurchaseOrderLineInput, PurchaseOrderLinePatch, PurchaseOrderPatch, ReceiveInput
from app.schemas.views import PurchaseOrderDetail, PurchaseOrderSummary
from app.services import purchasing

router = APIRouter(prefix="/api/purchase-orders", tags=["purchasing"])


@router.get("", response_model=list[PurchaseOrderSummary] | Page[PurchaseOrderSummary])
async def list_purchase_orders(
    lq: ListDep,
    status: str | None = Query(None, description="Comma list of statuses"),
    supplier_id: str | None = Query(None, alias="supplierId"),
    date: str | None = Query(None, description="Expected date YYYY-MM-DD"),
    q: str | None = Query(None, description="Number or supplier name"),
):
    """Newest first. sort: number | supplier | date (expected) | createdAt | lines | total | status.
    Envelope extras: counts (per status, ignoring `status`), sums.totalHt."""
    return purchasing.list_purchase_orders(lq, status=status, supplier_id=supplier_id or None, date=date or None, q=q or None)


@router.get("/{id}", response_model=PurchaseOrderDetail)
async def get_purchase_order(id: str):
    return purchasing.po_detail(id)


@router.post("", response_model=PurchaseOrderDetail, status_code=201)
async def create_purchase_order(body: PurchaseOrderInput, ctx: CtxDep):
    """Draft; prices from the supplier price list; lines may be empty."""
    return purchasing.create_purchase_order(ctx, body.data())


@router.patch("/{id}", response_model=PurchaseOrderDetail)
async def update_purchase_order(id: str, ctx: CtxDep, body: PurchaseOrderPatch | None = None):
    return purchasing.update_purchase_order(ctx, id, data(body))


@router.post("/{id}/lines", response_model=PurchaseOrderDetail, status_code=201)
async def add_purchase_line(id: str, body: PurchaseOrderLineInput, ctx: CtxDep):
    return purchasing.add_purchase_line(ctx, id, body.data())


@router.patch("/{id}/lines/{line_id}", response_model=PurchaseOrderDetail)
async def update_purchase_line(id: str, line_id: str, ctx: CtxDep, body: PurchaseOrderLinePatch | None = None):
    return purchasing.update_purchase_line(ctx, id, line_id, data(body))


@router.delete("/{id}/lines/{line_id}", response_model=PurchaseOrderDetail)
async def delete_purchase_line(id: str, line_id: str, ctx: CtxDep):
    return purchasing.delete_purchase_line(ctx, id, line_id)


@router.post("/{id}/send", response_model=PurchaseOrderDetail)
async def send_purchase_order(id: str, ctx: CtxDep):
    return purchasing.send_purchase_order(ctx, id)


@router.post("/{id}/receive", response_model=PurchaseOrderDetail)
async def receive_purchase_order(id: str, ctx: CtxDep, body: ReceiveInput | None = None):
    """Creates one lot per line received (expiry = today + shelf life)."""
    return purchasing.receive_purchase_order(ctx, id, data(body).get("lines"))


@router.post("/{id}/cancel", response_model=PurchaseOrderDetail)
async def cancel_purchase_order(id: str, ctx: CtxDep):
    return purchasing.cancel_purchase_order(ctx, id)
