"""/api/orders: sales orders and their lifecycle (draft → confirmed → prepared → delivered → invoiced)."""

from fastapi import APIRouter, Query

from app.core.listing import ListDep, Page
from app.dependencies import CtxDep, data
from app.schemas.inputs import OrderInput, OrderLineInput, OrderLinePatch, OrderPatch, PrepareInput
from app.schemas.views import InvoiceDetail, OrderDetail, OrderSummary
from app.services import orders

router = APIRouter(prefix="/api/orders", tags=["orders"])


@router.get("", response_model=list[OrderSummary] | Page[OrderSummary])
async def list_orders(
    lq: ListDep,
    status: str | None = Query(None, description="Comma list of statuses"),
    client_id: str | None = Query(None, alias="clientId"),
    date: str | None = Query(None, description="Delivery date YYYY-MM-DD"),
    q: str | None = Query(None, description="Order number or client name"),
    source: str | None = Query(None, description="Comma list of channels (manual, phone, voice_agent…)"),
    ids: str | None = Query(None, description="Comma list of order ids"),
):
    """Newest delivery date first. sort: number | client | date | createdAt | lines | total | status.
    Envelope extras: counts (per status, ignoring `status`), sums.totalHt."""
    return orders.list_orders(lq, status=status, client_id=client_id or None, date=date or None, q=q or None, source=source, ids=ids)


@router.get("/{id}", response_model=OrderDetail)
async def get_order(id: str):
    return orders.order_detail(id)


@router.post("", response_model=OrderDetail, status_code=201)
async def create_order(body: OrderInput, ctx: CtxDep):
    """Draft order; line prices resolved (client price > rules > list price)."""
    return orders.create_order(ctx, body.data())


@router.patch("/{id}", response_model=OrderDetail)
async def update_order(id: str, ctx: CtxDep, body: OrderPatch | None = None):
    """Draft/confirmed only."""
    return orders.update_order(ctx, id, data(body))


@router.post("/{id}/lines", response_model=OrderDetail, status_code=201)
async def add_order_line(id: str, body: OrderLineInput, ctx: CtxDep):
    return orders.add_line(ctx, id, body.data())


@router.patch("/{id}/lines/{line_id}", response_model=OrderDetail)
async def update_order_line(id: str, line_id: str, ctx: CtxDep, body: OrderLinePatch | None = None):
    return orders.update_line(ctx, id, line_id, data(body))


@router.delete("/{id}/lines/{line_id}", response_model=OrderDetail)
async def delete_order_line(id: str, line_id: str, ctx: CtxDep):
    return orders.delete_line(ctx, id, line_id)


@router.post("/{id}/confirm", response_model=OrderDetail)
async def confirm_order(id: str, ctx: CtxDep):
    """Checks client, credit limit, stock (→ warnings), reserves stock, assigns the route run."""
    return orders.confirm_order(ctx, id)


@router.post("/{id}/prepare", response_model=OrderDetail)
async def prepare_order(id: str, ctx: CtxDep, body: PrepareInput | None = None):
    return orders.prepare_order(ctx, id, data(body).get("lines"))


@router.post("/{id}/deliver", response_model=OrderDetail)
async def deliver_order(id: str, ctx: CtxDep):
    """Consumes lots FEFO, writes stock movements, marks the stop delivered."""
    return orders.deliver_order(ctx, id)


@router.post("/{id}/invoice", response_model=InvoiceDetail, status_code=201)
async def invoice_order(id: str, ctx: CtxDep):
    return orders.invoice_from_order(ctx, id)


@router.post("/{id}/cancel", response_model=OrderDetail)
async def cancel_order(id: str, ctx: CtxDep):
    """Releases the reservation."""
    return orders.cancel_order(ctx, id)
