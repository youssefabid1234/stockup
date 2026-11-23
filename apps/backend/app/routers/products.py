"""/api/products: catalogue with stock, detail, alternatives, edit (price, cost, tags…)."""

from fastapi import APIRouter, Query

from app.core.listing import ListDep, Page
from app.dependencies import CtxDep, data
from app.schemas.domain import Product
from app.schemas.inputs import ProductPatch
from app.schemas.views import ProductDetail, ProductSummary
from app.services import catalog, tags

router = APIRouter(prefix="/api/products", tags=["catalogue"])


@router.get("", response_model=list[ProductSummary] | Page[ProductSummary])
async def list_products(
    lq: ListDep,
    q: str | None = Query(None, description="Name, SKU, alias or origin"),
    category: str | None = Query(None, description="Comma list of categories"),
    tag: str | None = None,
    active: str | None = Query(None, description="true | false"),
):
    """By name. sort: name | sku | category | tags | price | cost | margin | available | expiry.
    Envelope extras: counts (per category, ignoring `category`)."""
    return catalog.list_products(lq, q=q or None, category=category or None, tag=tag or None, active=active or None)


@router.get("/{id}", response_model=ProductDetail)
async def get_product(id: str):
    return catalog.product_detail(id)


@router.get("/{id}/alternatives", response_model=list[ProductSummary])
async def product_alternatives(id: str):
    """Substitutes: same category, available stock, closest price first."""
    return catalog.alternatives(id)


@router.patch("/{id}", response_model=Product)
async def update_product(id: str, ctx: CtxDep, body: ProductPatch | None = None):
    return tags.update_product(ctx, id, data(body))
