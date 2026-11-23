"""/api/tags (groups), /api/price-rules, /api/prices (resolve, grid)."""

from fastapi import APIRouter, Query

from app.core.errors import validation_error
from app.core.utils import js_number
from app.core.listing import ListDep, Page
from app.dependencies import CtxDep, data, iso_date_query
from app.schemas.domain import PriceRule, TagDef, TagScope
from app.schemas.inputs import PriceRuleInput, PriceRulePatch, TagInput, TagPatch
from app.schemas.views import Ok, PriceGridRow, PriceRuleSummary, ResolvedPrice, TagWithCount
from app.services import pricing, tags as tag_service

tags = APIRouter(prefix="/api/tags", tags=["pricing"])
price_rules = APIRouter(prefix="/api/price-rules", tags=["pricing"])
prices = APIRouter(prefix="/api/prices", tags=["pricing"])


@tags.get("", response_model=list[TagWithCount])
async def list_tags(scope: str | None = Query(None, description="client | supplier | product")):
    """Group definitions with usage counts."""
    return tag_service.list_tags(scope or None)


@tags.post("", response_model=TagDef, status_code=201)
async def create_tag(body: TagInput, ctx: CtxDep):
    return tag_service.create_tag(ctx, body.data())


@tags.patch("/{scope}/{id}", response_model=TagDef)
async def update_tag(scope: TagScope, id: str, ctx: CtxDep, body: TagPatch | None = None):
    return tag_service.update_tag(ctx, scope, id, data(body))


@tags.delete("/{scope}/{id}", response_model=Ok)
async def delete_tag(scope: TagScope, id: str, ctx: CtxDep):
    """Also removes the tag from every entity of that scope."""
    return tag_service.delete_tag(ctx, scope, id)


@price_rules.get("", response_model=list[PriceRuleSummary] | Page[PriceRuleSummary])
async def list_price_rules(
    lq: ListDep,
    active: str | None = Query(None, description="true | false"),
    client_id: str | None = Query(None, alias="clientId"),
    product_id: str | None = Query(None, alias="productId"),
):
    """clientId / productId keep the rules that target them."""
    return pricing.list_price_rules(active=active, client_id=client_id, product_id=product_id, lq=lq)


@price_rules.post("", response_model=PriceRule, status_code=201)
async def create_price_rule(body: PriceRuleInput, ctx: CtxDep):
    return pricing.create_price_rule(ctx, body.data())


@price_rules.patch("/{id}", response_model=PriceRule)
async def update_price_rule(id: str, ctx: CtxDep, body: PriceRulePatch | None = None):
    return pricing.update_price_rule(ctx, id, data(body))


@price_rules.delete("/{id}", response_model=Ok)
async def delete_price_rule(id: str, ctx: CtxDep):
    return pricing.delete_price_rule(ctx, id)


@prices.get("/resolve", response_model=ResolvedPrice)
async def resolve_price(
    client_id: str | None = Query(None, alias="clientId"),
    product_id: str | None = Query(None, alias="productId"),
    qty: str | None = None,
    date: str | None = None,
):
    """The price an order line would get, and why."""
    if not client_id or not product_id:
        raise validation_error("clientId.productId: clientId et productId requis")
    return pricing.resolve_price(client_id, product_id, js_number(qty) if qty else 1, iso_date_query(date))


@prices.get("/grid", response_model=list[PriceGridRow])
async def price_grid(
    client_id: str | None = Query(None, alias="clientId"),
    client_tag: str | None = Query(None, alias="clientTag"),
    product_tag: str | None = Query(None, alias="productTag"),
    category: str | None = None,
    q: str | None = None,
):
    """Resolved price of every active product for one client (clientId) or one client group (clientTag)."""
    return pricing.price_grid(client_id=client_id, client_tag=client_tag, product_tag=product_tag, category=category, q=q)
