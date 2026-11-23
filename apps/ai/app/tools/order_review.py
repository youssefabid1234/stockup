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
    confirmer (« askFirst »), « canConfirm » (false = ne pas confirmer), brouillons en double de l'appel à abandonner
    (« duplicateDrafts ») et autres commandes du client pour le même jour (« sameDayOrders »). Read-back before confirming.
    """
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
    qty: float | None = Field(None, description="Quantité telle que dite par le client (défaut 1)"),
    said_unit: str | None = Field(None, description="L'unité dite : « cartons », « plaques », « kilos », « sacs »… (vide = unité de vente)"),
) -> dict:
    """
    Prix à dire au client, calculé (jamais de tête) : prix client à l'unité de vente + par conditionnement (carton, plaque, sac…)
    dans « say », et le total HT pour la quantité dans « total ». Ex. 3 cartons de tourage → « 9 euros 20 le kilo, soit 92 euros
    le carton de 10 kilos » et « 276 euros hors taxes pour 30 kilos, soit 3 cartons ». Spoken price quote, computed.
    """
    from app.agent.rules_order import quote, to_selling_qty  # here, not at the top: app.agent imports the tools package

    products = await products_by_id(ctx)
    p = products.get(product_id)
    if not p:
        raise ValueError(f"produit {product_id} introuvable : cherche-le d'abord avec search")
    q = to_selling_qty(qty or 1, said_unit, p["unit"], p.get("caliber") or "", p["name"])
    r = await ctx.erp.get("/api/prices/resolve", {"clientId": client_id, "productId": product_id, "qty": q})
    out = quote(qty or 1, p["unit"], p.get("caliber") or "", p["name"], r["price"], said_unit)
    if r.get("source") != "list":
        out["why"] = r.get("explanation")  # negotiated price / group rule: worth saying
    return out
