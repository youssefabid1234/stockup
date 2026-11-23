"""Home dashboard. Revenue = totalHt of sale orders (not draft/cancelled) by delivery date, up to today."""

from __future__ import annotations

import math

from app import crud
from app.core.activity import today
from app.core.db import Doc, per_data_version
from app.core.utils import add_days, cmp, round2, sort_by, to_date
from app.services.clients import is_sale
from app.services.invoices import balance_of, effective_status
from app.services.stock import line_qty, stock_levels


@per_data_version
def dashboard() -> Doc:
    """Cached until the next write (one pass over every order, invoice and lot)."""
    return _dashboard()


@per_data_version
def low_stock_ids() -> set[str]:
    """Every product in low stock (dashboard rule, not capped at 15): the stock list's "low" tab."""
    return {item["productId"] for _, item in _low_stock()}


def _sold14() -> dict[str, float]:
    t = today()
    sold14: dict[str, float] = {}
    for o in crud.orders.rows.values():
        if not is_sale(o) or o["deliveryDate"] > t or o["deliveryDate"] <= add_days(t, -14):
            continue
        for l in o["lines"]:
            sold14[l["productId"]] = sold14.get(l["productId"], 0) + line_qty(l)
    return sold14


def _low_stock(sold14: dict[str, float] | None = None) -> list[tuple[float, Doc]]:
    """(coverage in days, item) of products whose available stock covers less than 2 days of average sales
    (or nothing left), lowest coverage first."""
    sold14 = _sold14() if sold14 is None else sold14
    levels = stock_levels()
    low = []
    for p in crud.products.all():
        if not p["active"]:
            continue
        available = levels[p["id"]]["available"] if p["id"] in levels else 0
        daily = sold14.get(p["id"], 0) / 14
        coverage = available / daily if daily > 0 else (math.inf if available > 0 else 0)
        if available <= 0 or (daily > 0 and coverage < 2):
            low.append((coverage, {"productId": p["id"], "name": p["name"], "available": available, "unit": p["unit"]}))
    return sort_by(low, lambda a, b: cmp(a[0], b[0]))


def _dashboard() -> Doc:
    t = today()
    from30 = add_days(t, -29)  # 30 days including today
    month_start = f"{t[:7]}-01"

    by_day = {add_days(from30, i): 0.0 for i in range(30)}
    by_client: dict[str, float] = {}
    sold14: dict[str, float] = {}  # qty per product over 14 days, for low-stock coverage
    revenue_today = revenue_month = 0.0
    orders_today = draft_orders = to_deliver_today = 0

    for o in crud.orders.rows.values():
        if o["status"] == "draft":
            draft_orders += 1
        if o["status"] != "cancelled" and to_date(o["createdAt"]) == t:
            orders_today += 1
        if o["deliveryDate"] == t and o["status"] in ("confirmed", "prepared"):
            to_deliver_today += 1
        if not is_sale(o) or o["deliveryDate"] > t:
            continue
        if o["deliveryDate"] == t:
            revenue_today += o["totalHt"]
        if o["deliveryDate"] >= month_start:
            revenue_month += o["totalHt"]
        if o["deliveryDate"] >= from30:
            by_day[o["deliveryDate"]] = by_day.get(o["deliveryDate"], 0) + o["totalHt"]
            by_client[o["clientId"]] = by_client.get(o["clientId"], 0) + o["totalHt"]
        if o["deliveryDate"] > add_days(t, -14):
            for l in o["lines"]:
                sold14[l["productId"]] = sold14.get(l["productId"], 0) + line_qty(l)

    overdue_amount = 0.0
    overdue_count = 0
    for inv in crud.invoices.rows.values():
        if effective_status(inv) == "overdue":
            overdue_count += 1
            overdue_amount += balance_of(inv)

    # Low stock: available covers less than 2 days of average sales (or nothing left of a product that sells).
    low_stock = [item for _, item in _low_stock(sold14)[:15]]

    # Lots expiring within 2 days (including those already past their date but still on hand).
    lots = crud.lots.filter(lambda l: l["qtyRemaining"] > 0 and l["expiresAt"] <= add_days(t, 2))
    expiring = []
    for l in sort_by(lots, lambda a, b: cmp(a["expiresAt"], b["expiresAt"]))[:20]:
        p = crud.products.get(l["productId"])
        expiring.append({"lotId": l["id"], "productId": l["productId"], "name": p["name"] if p else "?", "qtyRemaining": l["qtyRemaining"], "expiresAt": l["expiresAt"]})

    top = sort_by(by_client.items(), lambda a, b: cmp(b[1], a[1]))[:10]
    top_clients = []
    for client_id, revenue in top:
        c = crud.clients.get(client_id)
        top_clients.append({"clientId": client_id, "name": c["name"] if c else "?", "revenue": round2(revenue)})

    return {
        "today": t,
        "revenueToday": round2(revenue_today),
        "revenueMonth": round2(revenue_month),
        "ordersToday": orders_today,
        "draftOrders": draft_orders,
        "toDeliverToday": to_deliver_today,
        "overdueInvoicesAmount": round2(overdue_amount),
        "overdueInvoicesCount": overdue_count,
        "lowStock": low_stock,
        "expiringSoon": expiring,
        "revenueByDay": [{"date": d, "revenue": round2(r)} for d, r in by_day.items()],
        "topClients": top_clients,
    }
