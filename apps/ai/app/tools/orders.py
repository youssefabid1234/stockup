"""Write tools: build an order step by step (draft → lines → confirm). Business rules live in the ERP API."""

from pydantic import Field

from .erp import enc, pick
from .history import without_none
from .registry import ToolArgs, ToolContext, tool


class OrderLine(ToolArgs):
    product_id: str
    qty: float = Field(description="Quantity in the unit of the product (kg, piece, box...)")
    note: str | None = Field(None, description="e.g. \"deliver before 7 a.m.\", \"well mature\"")
    substitute_for: str | None = Field(None, description="productId replaced, if it is a substitution")

    def to_erp(self) -> dict:
        return self.model_dump(by_alias=True, exclude_none=True)


def summarize_order(o: dict) -> dict:
    """What the model gets back after any order operation: short, with line ids for later edits."""
    return {
        **pick(o, "id", "number", "status"),
        "client": (o.get("client") or {}).get("name"),
        **pick(o, "deliveryDate", "totalHt"),
        "lines": [
            {
                "lineId": line["id"],
                **pick(line, "productId", "productName", "qty", "unit", "unitPrice", "available"),
                **({"note": line["note"]} if line.get("note") else {}),
            }
            for line in o["lines"]
        ],
        "warnings": o.get("warnings") or [],
    }


@tool
async def create_draft_order(
    ctx: ToolContext,
    client_id: str,
    delivery_date: str | None = Field(None, description="YYYY-MM-DD, optional"),
    lines: list[OrderLine] | None = None,
    note: str | None = None,
) -> dict:
    """
    Creates a pre-order (bruillon) for a customer, with or without lines. Price solved by the customerERP (prix client > catalogue).
    Create a draft order. Delivery date defaults to the client's next delivery day.
    """
    body = {
        "clientId": client_id,
        "deliveryDate": delivery_date,
        "lines": [line.to_erp() for line in lines] if lines is not None else None,
        "note": note,
        "source": "voice_agent" if ctx.actor == "voice_agent" else "web",
    }
    return summarize_order(await ctx.erp.post("/api/orders", without_none(body)))


@tool
async def add_order_line(
    ctx: ToolContext,
    order_id: str,
    product_id: str,
    qty: float = Field(description="Quantity in the unit of the product (kg, piece, box...)"),
    note: str | None = Field(None, description="e.g. \"deliver before 7 a.m.\", \"well mature\""),
    substitute_for: str | None = Field(None, description="productId replaced, if it is a substitution"),
) -> dict:
    """Add a line to a draft or confirmed command. Add a line to an order."""
    line = OrderLine(product_id=product_id, qty=qty, note=note, substitute_for=substitute_for)
    return summarize_order(await ctx.erp.post(f"/api/orders/{enc(order_id)}/lines", line.to_erp()))


@tool
async def confirm_order(ctx: ToolContext, order_id: str) -> dict:
    """
    Confirms an order: reserves the stock and assigns it to a tour. Returns alerts (in progress, stock...).
    Only after the caller explicitly agreed to the recap.
    """
    return summarize_order(await ctx.erp.post(f"/api/orders/{enc(order_id)}/confirm"))


@tool
async def get_order(ctx: ToolContext, order_id: str) -> dict:
    """Detail of an order (lines, status, total, alerts). Order detail."""
    return summarize_order(await ctx.erp.get(f"/api/orders/{enc(order_id)}"))
