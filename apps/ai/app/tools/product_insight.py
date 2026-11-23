"""
OWNER: Youssef · switch TEAM_PRODUCT_INSIGHT (registered only when on, restart needed) · contract: interfaces.md §2

One tool instead of four round-trips: product + stock + this client's price + substitutes (with their stock, price
and promo) in a single call, fetched in parallel. Real life: one glance at Lucie's screen tells her everything.

Today the model chains search → get_product_stock → get_price → find_alternatives (+ get_price per alternative):
4 to 6 model↔ERP round-trips ≈ 1 s each. This tool = 1 round-trip.

Output shape (the contract Daycem's rules_sales.rank_alternatives() works on):
    {
      "product": {id, name, unit, available, clientPrice, listPrice, priceExplanation},
      "inStock": bool,                       # available >= qty
      "alternatives": [ {id, name, unit, available, clientPrice, listPrice, promo?} ]  # best first
    }
"""

from __future__ import annotations

from pydantic import Field

from .registry import ToolContext, tool


@tool
async def product_insight(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0012"),
    product_id: str = Field(description="ex. prd_0025"),
    qty: float | None = Field(None, description="Quantité demandée dans l'unité du produit"),
) -> dict:
    """
    Tout sur un produit pour CE client en un seul appel : stock disponible, prix client, et remplaçants en stock avec leur
    prix et leurs promotions. À utiliser dès qu'un client demande un produit (au lieu de get_product_stock + get_price +
    find_alternatives). Product + stock + client price + substitutes in one call.
    """
    # TODO(Youssef): asyncio.gather of /api/products/{id}, /api/prices/resolve, /api/products/{id}/alternatives,
    # then /api/prices/resolve for each alternative (in parallel); promos from the price rules; rank with
    # app.agent.rules_sales.rank_alternatives (Daycem) once it exists.
    raise NotImplementedError("product_insight: TODO(Youssef)")
