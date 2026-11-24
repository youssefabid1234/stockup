"""
OWNER: Youssef · switch TEAM_PRODUCT_INSIGHT (registered only when on, restart needed) · contract: interfaces.md §2

One tool instead of four round-trips: product + stock + this client's price + substitutes (with their stock, price
and promo) in a single call, fetched in parallel. Real life: one glance at Lucie's screen tells her everything.

Without it the model chains get_product_stock → get_price → find_alternatives (+ get_price per alternative):
4 to 6 model↔ERP round-trips ≈ 1 s each. This tool = 1 round-trip. The logic lives in insight.py (testable alone).

Output shape (the contract Daycem's rules_sales.rank_alternatives() works on):
    {
      "product": {id, name, unit, available, clientPrice, listPrice, priceExplanation, promo?, betterPriceWithVolume?},
      "inStock": bool,                       # available >= qty
      "missing"?: number,                    # short but some left
      "substitution"?: refuse|accepte|demander|inconnu   # only when short (Daycem's substitution_policy)
      "alternatives": [ {id, name, unit, available, clientPrice, listPrice, promo?} ]  # best first, [] if in stock
    }
"""

from __future__ import annotations

from pydantic import Field

from .insight import gather_insight
from .registry import ToolContext, tool


@tool
async def product_insight(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0012"),
    product_id: str = Field(description="ex. prd_0025"),
    qty: float | None = Field(None, description="Quantité demandée dans l'unité du produit"),
) -> dict:
    """
    Tout sur un produit pour CE client en un seul appel : stock disponible, prix client, et s'il manque, remplaçants en
    stock déjà classés (le premier est le meilleur) avec leur prix et leurs promotions, et si le client accepte un
    remplacement. À utiliser dès qu'un client demande un produit (au lieu de get_product_stock + get_price +
    find_alternatives). Product + stock + client price + ranked substitutes in one call.
    """
    return await gather_insight(ctx.erp, client_id, product_id, qty)
