"""Read-only tools: find things, look at a client, check stock and prices, suggest substitutes."""

from typing import Literal

from pydantic import Field

from .erp import enc, pick
from .history import compact_event
from .registry import ToolContext, tool


@tool
async def search(
    ctx: ToolContext,
    query: str = Field(description="Ce que l'utilisateur a dit, ex. un nom de client approximatif (« bistrot du port »), un produit tel que dit, « CMD-2026-000123 »"),
    types: list[Literal["client", "product", "supplier", "order"]] | None = Field(
        None, description="Optionnel : restreindre les types"
    ),
) -> list[dict]:
    """
    Recherche floue (accents, fautes, surnoms de produits) dans l'ERP : clients, produits, fournisseurs, commandes.
    Fuzzy search for clients/products/suppliers/orders. Returns ids to use with the other tools.
    """
    results = await ctx.erp.get("/api/search", {"q": query, "types": ",".join(types) if types else None})
    return [pick(r, "type", "id", "label", "sublabel") for r in results[:8]]


CLIENT_FIELDS = ("id", "name", "type", "status", "city", "deliveryDays", "paymentTermsDays", "creditLimit", "outstanding", "overdue", "contacts", "preferences")  # fmt: skip


@tool
async def get_client(ctx: ToolContext, client_id: str = Field(description="ex. cli_0012")) -> dict:
    """
    Fiche client : statut, conditions, encours, préférences, notes des commerciaux, « l'habituel » (ce qu'il commande d'habitude),
    problèmes ouverts et 5 derniers événements de l'historique (get_client_history pour tout l'historique).
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
    Stock d'un produit : disponible (= physique - réservé), arrivages attendus, prochaine DLC, prix catalogue.
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
    Produits de remplacement disponibles (même catégorie, prix proche) quand un produit manque.
    Substitutes in stock for a product. Check the client's notes before proposing a substitution.
    """
    alternatives = await ctx.erp.get(f"/api/products/{enc(product_id)}/alternatives")
    return [pick(p, "id", "name", "unit", "price", "available") for p in alternatives[:5]]


@tool
async def get_price(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0012"),
    product_id: str = Field(description="ex. prd_0042"),
    qty: float | None = Field(None, description="Quantité (défaut 1) : certaines règles dépendent du volume"),
) -> dict:
    """
    Prix de vente d'un produit pour un client (HT, par unité), tel qu'une ligne de commande le recevrait : prix négocié > règle de prix
    (groupe de clients, groupe/catégorie de produits, quantité minimale) > prix catalogue, avec l'explication. À utiliser pour annoncer un prix.
    Resolved sell price for a client and quantity, with a French explanation.
    """
    query = {"clientId": client_id, "productId": product_id, "qty": format_number(qty) if qty else None}
    r = await ctx.erp.get("/api/prices/resolve", query)
    # A volume rule that would give a better price: worth telling the client.
    volume = next(
        (
            c
            for c in r["candidates"]
            if c.get("source") == "rule" and (c.get("reason") or "").startswith("à partir de") and c["price"] < r["price"]
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
