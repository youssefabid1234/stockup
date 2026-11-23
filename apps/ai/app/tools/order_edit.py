"""
OWNER: Amine Khalil · switch TEAM_ORDER_RULES (registered only when it is on)

Changing one's mind on the phone (« finalement 12 », « enlève le seigle », « plutôt vendredi », « laisse tomber »):
the kit could only ADD lines, so the agent created a second order and left the first draft behind (seen in S31).
These tools edit the existing order through the ERP's own routes (PATCH / DELETE a line, PATCH the order,
cancel a draft). The ERP keeps its rules (allowed statuses, positive quantities); errors come back as messages.
"""

from pydantic import Field

from .erp import enc
from .orders import summarize_order
from .registry import ToolContext, tool


@tool
async def update_order_line(
    ctx: ToolContext,
    order_id: str,
    line_id: str = Field(description="lineId renvoyé par create_draft_order / get_order"),
    qty: float | None = Field(None, description="Nouvelle quantité, dans l'unité du produit"),
    product_id: str | None = Field(None, description="Autre produit à la place (seulement si le client l'a demandé)"),
    note: str | None = None,
) -> dict:
    """
    Modifie une ligne existante d'une commande (brouillon ou confirmée) : quantité, produit ou note. Pour un changement d'avis
    (« finalement 12 ») : modifie la ligne, n'en ajoute pas une deuxième. Change the quantity/product of an order line.
    """
    patch = {k: v for k, v in {"qty": qty, "productId": product_id, "note": note}.items() if v is not None}
    if not patch:
        raise ValueError("rien à modifier : donne qty, product_id ou note")
    return summarize_order(await ctx.erp.patch(f"/api/orders/{enc(order_id)}/lines/{enc(line_id)}", patch))


@tool
async def remove_order_line(ctx: ToolContext, order_id: str, line_id: str = Field(description="lineId à retirer")) -> dict:
    """Retire une ligne d'une commande (« enlève le seigle », « finalement pas de beurre »). Remove an order line."""
    return summarize_order(await ctx.erp.delete(f"/api/orders/{enc(order_id)}/lines/{enc(line_id)}"))


@tool
async def change_delivery_date(
    ctx: ToolContext, order_id: str, delivery_date: str = Field(description="YYYY-MM-DD, vérifiée avec check_delivery_date")
) -> dict:
    """Change le jour de livraison d'une commande (« plutôt vendredi »). Vérifie d'abord le jour avec check_delivery_date."""
    return summarize_order(await ctx.erp.patch(f"/api/orders/{enc(order_id)}", {"deliveryDate": delivery_date}))


@tool
async def cancel_draft_order(ctx: ToolContext, order_id: str) -> dict:
    """
    Abandonne un BROUILLON (le client renonce, ou un brouillon créé par erreur en double). Refuse une commande déjà confirmée :
    ça, c'est à l'équipe. Drop a draft order.
    """
    order = await ctx.erp.get(f"/api/orders/{enc(order_id)}")
    if order.get("status") != "draft":
        raise ValueError(f"{order.get('number')} est « {order.get('status')} » : seule une commande brouillon peut être abandonnée ici")
    return summarize_order(await ctx.erp.post(f"/api/orders/{enc(order_id)}/cancel"))
