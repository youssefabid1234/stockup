"""Recommendations consumed by the voice session. Offer writes recheck the ERP snapshot."""

import os

from fastapi import APIRouter, Depends, Query
from pydantic import Field

from app.core.errors import not_found
from app.dependencies import CtxDep
from app.schemas.base import Input, Schema
from app.schemas.views import OrderDetail
from app.services import recommendations

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


def enabled() -> bool:
    return os.environ.get("TEAM_RECOMMENDATIONS", "").strip().lower() in {"1", "true", "yes", "on"}


def require_enabled() -> None:
    if not enabled():
        raise not_found("Fonctionnalité", "suggestions")


class Offer(Schema):
    id: str
    product_id: str
    product_name: str
    kind: str
    unit: str
    caliber: str | None = None
    quantity: float
    unit_price: float
    delivery_date: str
    rule_id: str | None = None
    valid_until: str | None = None
    purchase_count: int
    co_purchase_count: int
    last_purchased_on: str | None = None


class AcceptOffer(Input):
    offer: Offer
    quantity: float = Field(gt=0, allow_inf_nan=False)
    order_id: str | None = None
    request_id: str = Field(min_length=1, max_length=128)


@router.get("", response_model=list[Offer], dependencies=[Depends(require_enabled)])
async def list_recommendations(client_id: str = Query(alias="clientId"), order_id: str | None = Query(None, alias="orderId")):
    return recommendations.select(client_id, order_id)


@router.post("/{client_id}/accept", response_model=OrderDetail, dependencies=[Depends(require_enabled)])
async def accept_recommendation(client_id: str, body: AcceptOffer, ctx: CtxDep):
    offer = body.offer.model_dump(by_alias=True, exclude_none=False)
    return recommendations.add_offer(ctx, client_id, offer, body.quantity, body.order_id, body.request_id)


@router.post("/{client_id}/decline", dependencies=[Depends(require_enabled)])
async def decline_recommendation(client_id: str, body: Offer, ctx: CtxDep):
    recommendations.decline(ctx, client_id, body.model_dump(by_alias=True))
    return {"ok": True}
