"""
OWNER: Amine Khalil · switch TEAM_ORDER_RULES (registered only when it is on) · see agent/rules_order.py (review)

review_order: what Lucie does before saying « je vous relis la commande » — the order in spoken words, the ERP's
warnings translated for the caller (internal ones dropped), the 150 € franco note, the unusual quantities to have
confirmed, and whether the order may be confirmed. Deterministic, 3 small ERP reads in parallel.
"""

import asyncio
import time

from pydantic import Field

from .erp import enc
from .registry import ToolContext, tool

_products: tuple[float, dict[str, dict]] | None = None


async def products_by_id(ctx: ToolContext) -> dict[str, dict]:
    """The catalogue (71 products), cached 10 minutes: we only need names, units and package words."""
    global _products
    if _products and time.monotonic() - _products[0] < 600:
        return _products[1]
    rows = await ctx.erp.get("/api/products", {"limit": 500})
    rows = rows.get("items", rows) if isinstance(rows, dict) else rows
    _products = (time.monotonic(), {p["id"]: p for p in rows})
    return _products[1]


@tool
async def review_order(ctx: ToolContext, order_id: str = Field(description="ex. ord_024770 (renvoyé par create_draft_order)")) -> dict:
    """
    À appeler après avoir créé ou modifié une commande, avant de la relire au client : phrase de relecture prête à dire
    (« readback »), alertes à dire au client (« alerts »), remarque franco 150 € (« franco »), quantités inhabituelles à faire
    confirmer (« askFirst ») et « canConfirm » (false = ne pas confirmer). Read-back of an order before confirming it.
    """
    from app.agent.rules_order import review  # here, not at the top: app.agent imports the tools package

    order = await ctx.erp.get(f"/api/orders/{enc(order_id)}")
    products, usual = await asyncio.gather(
        products_by_id(ctx), ctx.erp.get(f"/api/clients/{enc(order['clientId'])}/usual")
    )
    return review(order, products, usual or [])
