"""/api/stock: levels, movements, manual adjustments."""

from fastapi import APIRouter, Query

from app.core.listing import ListDep, Page
from app.dependencies import CtxDep
from app.schemas.domain import StockLevel, StockMovement
from app.schemas.inputs import StockAdjustInput
from app.schemas.views import StockItem
from app.services import stock

router = APIRouter(prefix="/api/stock", tags=["stock"])


@router.get("", response_model=list[StockItem] | Page[StockItem])
async def list_stock(
    lq: ListDep,
    q: str | None = Query(None, description="Product name, SKU or alias"),
    tab: str | None = Query(None, description="out | low | expiring"),
):
    """By product name. sort: product | sku | category | onHand | reserved | available | incoming | expiry | state.
    Envelope extras: counts per tab ("" = all, out, low, expiring; ignoring `tab`)."""
    return stock.list_stock(lq, q=q or None, tab=tab or None)


@router.get("/movements", response_model=list[StockMovement] | Page[StockMovement])
async def stock_movements(lq: ListDep, product_id: str | None = Query(None, alias="productId")):
    """Newest first (`order=asc`: oldest first)."""
    return stock.list_movements(product_id or None, lq=lq)


@router.post("/adjust", response_model=StockLevel)
async def adjust_stock(body: StockAdjustInput, ctx: CtxDep):
    """qty > 0 adds a lot; qty < 0 removes FEFO; reason "waste" always removes."""
    return stock.adjust_stock(ctx, body.data())
