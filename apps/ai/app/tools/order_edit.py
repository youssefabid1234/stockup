"""
OWNER: Amine Khalil · switch TEAM_ORDER_RULES (registered only when it is on)

Changing one's mind on the phone ("finally 12", "remove rye", "friday rather", "drop it"):
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
    line_id: str = Field(description="lineId sent back by create_draft_order / get_order"),
    qty: float | None = Field(None, description="New quantity, in the unit of the product"),
    product_id: str | None = Field(None, description="Other product instead (only if requested by the customer)"),
    note: str | None = None,
) -> dict:
    """
    Modify an existing line of an order (scratch or confirmed): quantity, product or note. For a change of opinion
    ("finally 12") : changes the line, does not add a second one. Change the quantity/product of an order line.
    """
    patch = {k: v for k, v in {"qty": qty, "productId": product_id, "note": note}.items() if v is not None}
    if not patch:
        raise ValueError("nothing to change: give qty, product_id or note")
    return summarize_order(await ctx.erp.patch(f"/api/orders/{enc(order_id)}/lines/{enc(line_id)}", patch))


@tool
async def remove_order_line(ctx: ToolContext, order_id: str, line_id: str = Field(description="lineId to be removed")) -> dict:
    """Remove a line from a command ("remove rye", "finally no butter"). Remove an order line."""
    return summarize_order(await ctx.erp.delete(f"/api/orders/{enc(order_id)}/lines/{enc(line_id)}"))


@tool
async def change_delivery_date(
    ctx: ToolContext, order_id: str, delivery_date: str = Field(description="YYYY-MM-DD, checked with check_delivery_date")
) -> dict:
    """Change the day of delivery of an order ("rather Friday"). First check the day with check_delivery_date."""
    return summarize_order(await ctx.erp.patch(f"/api/orders/{enc(order_id)}", {"deliveryDate": delivery_date}))


@tool
async def cancel_draft_order(ctx: ToolContext, order_id: str) -> dict:
    """
    Drop one BROUILLON (the client renounces, or a draft created by mistake in duplicate).
    Drop's got a draft order.
    """
    order = await ctx.erp.get(f"/api/orders/{enc(order_id)}")
    if order.get("status") != "draft":
        raise ValueError(f"{order.get('number')} is \" {order.get('status')} » : only a draft command can be dropped here")
    return summarize_order(await ctx.erp.post(f"/api/orders/{enc(order_id)}/cancel"))
