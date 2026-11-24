"""Read-only tools: find things, look at a client, check stock and prices, suggest substitutes."""

from typing import Literal

from pydantic import Field

from .erp import enc, pick
from .history import compact_event
from .registry import ToolContext, tool


@tool
async def search(
    ctx: ToolContext,
    query: str = Field(description="What the user said, e.g. an approximate customer name (\"port bistro\"), a product as said, \" CMD-2026-000123 »"),
    types: list[Literal["client", "product", "supplier", "order"]] | None = Field(
        None, description="Optional: restrict types"
    ),
) -> list[dict]:
    """
    Unsure search (accents, errors, product nicknames) in theERP : customers, products, suppliers, orders.
    Fuzzy search for clients/products/suppliers/orders. Returns ids to use with the other tools.
    """
    results = await ctx.erp.get("/api/search", {"q": query, "types": ",".join(types) if types else None})
    return [pick(r, "type", "id", "label", "sublabel") for r in results[:8]]


CLIENT_FIELDS = ("id", "name", "type", "status", "city", "deliveryDays", "paymentTermsDays", "creditLimit", "outstanding", "overdue", "contacts", "preferences")  # fmt: skip


@tool
async def get_client(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> dict:
    """
    Customer profile: status, conditions, stock, preferences, commercial notes, "usual" (which it usually orders),
    Open problems and 5 last events of history (get_client_history for the whole history).
    Client detail incl. usual basket, notes, open issues and latest history events.
    """
    c = await ctx.erp.get(f"/api/clients/{enc(client_id)}")
    stats = c.get("eventStats")
    return {
        **pick(c, *CLIENT_FIELDS),
        "notes": [f"{n['at'][:10]} {n['author']} : {n['text']}" for n in c["notes"][-5:]],
        "usual": [
            pick(u, "productId", "productName", "unit", "avgQty", "lastQty") for u in c["usual"][:10]
        ],
        **pick(c, "openIssues"),
        **({"history": pick(stats, "total", "since", "complaints12m", "returns12m")} if stats else {}),
        "recentEvents": [compact_event(e) for e in (c.get("recentEvents") or [])[:5]],
        "recentOrders": [
            pick(o, "id", "number", "status", "deliveryDate", "totalHt") for o in c["recentOrders"][:5]
        ],
    }


@tool
async def get_product_stock(ctx: ToolContext, product_id: str = Field(description="ex. prd_0042")) -> dict:
    """
    Stock of a product : available (= physical - reserved), expected arrivals, next DLC, catalogue price.
    Product stock, incoming, next expiry and list price.
    """
    p = await ctx.erp.get(f"/api/products/{enc(product_id)}")
    stock = p.get("stock") or {}
    return {
        **pick(p, "id", "name", "unit", "price", "origin", "caliber", "available", "onHand"),
        **pick(stock, "reserved", "incoming"),
        **pick(p, "nextExpiry"),
    }


@tool
async def find_alternatives(ctx: ToolContext, product_id: str) -> list[dict]:
    """
    Alternative products available (same category, near price) when a product is missing.
    Substitutes in stock for a product. Check the client's notes before proposing a substitution.
    """
    alternatives = await ctx.erp.get(f"/api/products/{enc(product_id)}/alternatives")
    return [pick(p, "id", "name", "unit", "price", "available") for p in alternatives[:5]]


@tool
async def get_price(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0012"),
    product_id: str = Field(description="ex. prd_0042"),
    qty: float | None = Field(None, description="Quantity (default 1): some rules depend on volume"),
) -> dict:
    """
    Sales price of a product for a customer (HT, par unité), tel qu'une ligne de commande le recevrait : prix négocié > règle de prix
    (groupe de clients, groupe/catégorie de produits, quantité minimale) > prix catalogue, avec l'explication. À utiliser pour annoncer un prix.
    Resolved sell price for a client and quantity, with a English explanation.
    """
    query = {"clientId": client_id, "productId": product_id, "qty": format_number(qty) if qty else None}
    r = await ctx.erp.get("/api/prices/resolve", query)
    # A volume rule that would give a better price: worth telling the client.
    volume = next(
        (
            c
            for c in r["candidates"]
            if c.get("source") == "rule" and (c.get("reason") or "").startswith("from") and c["price"] < r["price"]
        ),
        None,
    )
    return {
        **pick(r, "price", "listPrice", "source", "explanation"),
        **({"betterPriceWithVolume": f"{format_number(volume['price'])} € {volume['reason']}"} if volume else {}),
    }


def format_number(n: float) -> str:
    """5.0 → "5", 2.5 → "2.5" (like JavaScript's String(number))."""
    return str(int(n)) if float(n).is_integer() else str(n)
