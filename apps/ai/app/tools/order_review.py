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
async def review_order(ctx: ToolContext, order_id: str = Field(description="ex. ord_024770 (resented by create_draft_order)")) -> dict:
    """
    Calling after creating or modifying an order, before rereading it to the customer: read-back sentence ready to say
    (readback), alerts to tell the customer ("alerts"), remark franco 150 € ("franco"), unusual quantities to make
    confirm (" askFirst »), « canConfirm (false = do not confirm), drafts duplicated the call to abandon
    (« duplicateDrafts ) and other orders from the customer for the same day (" sameDayOrders »). Read-back before confirming.
    """
    return await review_for(ctx, order_id)


async def review_for(ctx: ToolContext, order_id: str) -> dict:
    """review_order's work, reusable by place_order (tools/order_place.py)."""
    from app.agent.rules_order import review  # here, not at the top: app.agent imports the tools package

    order = await ctx.erp.get(f"/api/orders/{enc(order_id)}")
    client_id = order["clientId"]
    products, usual, open_orders = await asyncio.gather(
        products_by_id(ctx),
        ctx.erp.get(f"/api/clients/{enc(client_id)}/usual"),
        ctx.erp.get("/api/orders", {"clientId": client_id, "status": "draft,confirmed,prepared", "limit": 50}),
    )
    open_orders = open_orders.get("items", open_orders) if isinstance(open_orders, dict) else open_orders or []
    # Other drafts made by the agent (rare: 0 or 1): load their lines so they can be read back / compared
    others = [o for o in open_orders if o["id"] != order_id and o.get("status") == "draft" and o.get("source") == "voice_agent"]
    details = await asyncio.gather(*(ctx.erp.get(f"/api/orders/{enc(o['id'])}") for o in others))
    by_id = {d["id"]: d for d in details}
    open_orders = [{**o, "lines": by_id[o["id"]]["lines"]} if o["id"] in by_id else o for o in open_orders]
    return review(order, products, usual or [], open_orders)


@tool
async def quote_line(
    ctx: ToolContext,
    client_id: str,
    product_id: str,
    qty: float | None = Field(None, description="Quantity as stated by the customer (default 1)"),
    said_unit: str | None = Field(None, description="The unit called \"cardboards\", \"plates\", \"kilos\", \"bags\"... (empty = sales unit)"),
) -> dict:
    """
    Price to be told to the customer, calculated (never in the lead): customer price per sales unit + per packaging (card, plate, bag...)
    in "say", and total HT for the quantity in "total". Ex. 3 turning cartons → "9 euros 20 per kilo, i.e. 92 euros
    le carton de 10 kilos » et « 276 euros hors taxes pour 30 kilos, soit 3 cartons ». Spoken price quote, computed.
    """
    from app.agent.rules_order import quote, to_selling_qty  # here, not at the top: app.agent imports the tools package

    products = await products_by_id(ctx)
    p = products.get(product_id)
    if not p:
        raise ValueError(f"produit {product_id} Not found: first search it with search")
    q = to_selling_qty(qty or 1, said_unit, p["unit"], p.get("caliber") or "", p["name"])
    r = await ctx.erp.get("/api/prices/resolve", {"clientId": client_id, "productId": product_id, "qty": q})
    out = quote(qty or 1, p["unit"], p.get("caliber") or "", p["name"], r["price"], said_unit)
    if r.get("source") != "list":
        out["why"] = r.get("explanation")  # negotiated price / group rule: worth saying
    return out
