"""
OWNER: Amine Khalil (T4 taken from Youssef) · switch TEAM_ORDER_RULES (registered only when it is on)

place_order: a whole order step in ONE tool call. Measured before (mar. 24/11): taking « dix sacs de tradi pour
jeudi » cost 3 to 4 model round trips (check_delivery_date + product_insight, then create_draft_order, then
review_order, then the answer), and each round trip re-reads the prompt and writes tokens. This tool does the
deterministic chain itself, in code: the delivery day (rules_order.delivery_answer), the products (catalogue alias
first, else Jev with the client's habits: resolve_product), the units (« 3 cartons » of tourage → 30 kg), the write
(create the draft, or edit the order in progress: change a quantity, remove a line at 0, move the day), then the
read-back (review: alerts, franco, unusual quantities, duplicates). The model then only answers.
It never writes when something is unclear: an unknown day, an ambiguous product, a blocked account → « next » says what
to ask, nothing is created.
"""

import asyncio  # no `from __future__ import annotations`: the tool registry needs the real PlaceLine type

from pydantic import Field

from .erp import enc
from .registry import ToolArgs, ToolContext, tool


class PlaceLine(ToolArgs):
    said: str | None = Field(None, description="The caller’s own words for the product")
    product_id: str | None = Field(None, description="If you already know him (prd_...); otherwise \"said\"")
    qty: float = Field(description="The quantity said. 0 = remove this product from the current order")
    said_unit: str | None = Field(None, description="Spoken unit, such as sacks, kilos, boxes or slabs")


@tool
async def place_order(
    ctx: ToolContext,
    client_id: str,
    lines: list[PlaceLine],
    delivery_day: str | None = Field(None, description="The day as said: \"Thursday\", \"Tomorrow\", \"The 27\" (empty = next possible day, or the day of the current order)"),
    order_id: str | None = Field(None, description="The current command to be modified (if not a new one is created)"),
) -> dict:
    """
    Takes or modifies an order in UN call: check the delivery day, find the products ("trade", "tourage"...),
    converts units, creates draft or modifies the current command (quantity, line 0 = removed, other day),
    then returns readback, alerts, franco, unusual quantities and
    canConfirm. If "next" is present, nothing has been written: ask the question it indicates. Take or change an order.
    """
    from app.agent.rules_order import delivery_answer, short_name, to_selling_qty

    from .delivery import pack_now
    from .order_jev import resolve_product
    from .order_review import products_by_id, review_for

    meta, client, catalogue = await asyncio.gather(
        ctx.erp.get("/api/meta"), ctx.erp.get(f"/api/clients/{enc(client_id)}"), products_by_id(ctx)
    )
    if client.get("status") == "blocked":
        return {"written": False, "blocked": True,
                "next": "Account blocked: do not take the order, promise nothing; say that accounting recalls and "
                        "records the application (log_client_event)."}

    order = await ctx.erp.get(f"/api/orders/{enc(order_id)}") if order_id else None
    if order and order.get("status") not in ("draft", "confirmed"):
        order, order_id = None, None  # prepared / delivered / cancelled: a new order

    # 1. The day: checked when said, or for a new order (the next possible day)
    date = order["deliveryDate"] if order else None
    say_day = None
    if delivery_day or not order:
        today, hour = pack_now(meta)
        day = delivery_answer(today, client.get("deliveryDays") or [], delivery_day, hour, client.get("zone"))
        if not day.get("ok"):
            return {"written": False, "day": day,
                    "next": f"Delivery unavailable ({day.get('reason')}). Offer {day.get('sayNext') or 'another day'}."}
        date, say_day = day["date"], day["say"]

    # 2. The products, in parallel (catalogue alias first, else Jev with the client's habits)
    async def find(line: PlaceLine) -> dict:
        if line.product_id and line.product_id in catalogue:
            return {"found": True, "productId": line.product_id}
        return await resolve_product.fn(ctx, client_id, line.said or "")

    found = await asyncio.gather(*(find(li) for li in lines))
    unclear = [f.get("ask") or f"What product for \" {li.said} » ?" for li, f in zip(lines, found, strict=True) if not f.get("found")]
    if unclear:
        return {"written": False, "next": " ".join(unclear)}

    # 3. The units → the selling unit; a non-whole number of sacks / cartons is asked, never rounded silently
    wanted: list[tuple[str, float]] = []
    for li, f in zip(lines, found, strict=True):
        p = catalogue[f["productId"]]
        qty = to_selling_qty(li.qty, li.said_unit, p["unit"], p.get("caliber") or "", p["name"])
        if p["unit"] in ("piece", "box") and qty != int(qty):
            return {"written": False,
                    "next": f"{li.qty:g} {li.said_unit or ''} of {short_name(p['name'])} = {qty:g} {p.get('caliber') or ''} : "
                            f"asks how many {(p.get('caliber') or 'Units').split()[0]}If he wants."}
        wanted.append((f["productId"], qty))

    # 4. The write: a new draft, or the order in progress edited (one order per call)
    if order:
        by_product = {line["productId"]: line for line in order["lines"]}
        writes = []
        for product_id, qty in wanted:
            line = by_product.get(product_id)
            if line and qty <= 0:
                writes.append(ctx.erp.delete(f"/api/orders/{enc(order_id)}/lines/{enc(line['id'])}"))
            elif line and qty != line["qty"]:
                writes.append(ctx.erp.patch(f"/api/orders/{enc(order_id)}/lines/{enc(line['id'])}", {"qty": qty}))
            elif not line and qty > 0:
                writes.append(ctx.erp.post(f"/api/orders/{enc(order_id)}/lines", {"productId": product_id, "qty": qty}))
        for w in writes:  # one after the other: the ERP rewrites the whole order on each change
            await w
        if date != order["deliveryDate"]:
            await ctx.erp.patch(f"/api/orders/{enc(order_id)}", {"deliveryDate": date})
    else:
        body = {"clientId": client_id, "deliveryDate": date, "source": "voice_agent",
                "lines": [{"productId": pid, "qty": q} for pid, q in wanted if q > 0]}
        if not body["lines"]:
            return {"written": False, "next": "No quantity: ask what he wants to order."}
        order_id = (await ctx.erp.post("/api/orders", body))["id"]

    # 5. The read-back, ready to say
    out = await review_for(ctx, order_id)
    return {"written": True, **({"daySay": say_day} if say_day else {}), **out}
