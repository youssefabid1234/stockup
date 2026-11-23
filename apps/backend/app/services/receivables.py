"""Receivables ("encours"): aged balance per client as of business today.

- balance = totalTtc − amountPaid on open invoices; buckets by days past dueDate ("current" = not yet due).
- avgDaysToPay: paid invoices whose final payment landed in the last 90 days (final payment date − issuedAt).
- risk: high if outstanding > credit limit, > 60 days overdue, client blocked, or (avgDaysToPay > 60 and something overdue);
        watch if > 80 % of limit, > 30 days overdue, an OPEN late_payment client event, or avgDaysToPay > 45.
- DSO = outstanding / TTC invoiced over the last 90 days × 90.
"""

from __future__ import annotations

from app import crud
from app.core.activity import today
from app.core.db import Doc
from app.core.utils import add_days, cmp, days_between, js_round, normalize, round2, round3, sort_by, total
from app.services.invoices import balance_of, is_open

BUCKETS = ["current", "d1_30", "d31_60", "d61_90", "d90plus"]


def _bucket_of(days_overdue: int) -> str:
    if days_overdue <= 0:
        return "current"
    if days_overdue <= 30:
        return "d1_30"
    if days_overdue <= 60:
        return "d31_60"
    return "d61_90" if days_overdue <= 90 else "d90plus"


def receivables(q: str | None = None, tag: str | None = None, rep: str | None = None,
                zone: str | None = None, only_overdue: str | None = None) -> Doc:  # fmt: skip
    t = today()
    from90 = add_days(t, -90)

    # Index once: open invoices per client, final payment date per invoice, last payment per client.
    open_by_client: dict[str, list[Doc]] = {}
    for inv in crud.invoices.all():
        if is_open(inv):
            open_by_client.setdefault(inv["clientId"], []).append(inv)
    paid_at: dict[str, str] = {}
    last_payment: dict[str, Doc] = {}
    for p in crud.payments.all():
        for a in p["allocations"]:
            if a["invoiceId"] not in paid_at or p["receivedAt"] > paid_at[a["invoiceId"]]:
                paid_at[a["invoiceId"]] = p["receivedAt"]
        lp = last_payment.get(p["clientId"])
        if not lp or p["receivedAt"] > lp["at"]:
            last_payment[p["clientId"]] = {"at": p["receivedAt"], "amount": p["amount"]}
    pay_days: dict[str, list[int]] = {}
    for inv in crud.invoices.all():
        when = paid_at.get(inv["id"])
        if inv["status"] != "paid" or not when or when < from90:
            continue
        pay_days.setdefault(inv["clientId"], []).append(max(0, days_between(inv["issuedAt"], when)))
    disputes: dict[str, int] = {}
    last_reminder: dict[str, str] = {}
    open_reminder: set[str] = set()
    for e in crud.client_events.all():
        if e["type"] == "dispute" and e.get("status") == "open":
            disputes[e["clientId"]] = disputes.get(e["clientId"], 0) + 1
        if e["type"] == "late_payment":
            if e.get("status") == "open":
                open_reminder.add(e["clientId"])
            d = e["at"][:10]
            if d > last_reminder.get(e["clientId"], ""):
                last_reminder[e["clientId"]] = d

    nq = normalize(q) if q else None
    nrep = normalize(rep) if rep else None
    overdue_only = only_overdue in ("true", "1")

    def matches(c: Doc) -> bool:
        return (
            (not nq or nq in normalize(f"{c['name']} {c['code']}"))
            and (not tag or tag in (c.get("tags") or []))
            and (not nrep or nrep in normalize(c["salesRep"]))
            and (not zone or c["zone"] == zone)
        )

    rows: list[Doc] = []
    for client_id, invs in open_by_client.items():
        c = crud.clients.get(client_id)
        if not c or not matches(c):
            continue
        buckets = {k: 0.0 for k in BUCKETS}
        max_days = 0
        oldest_due = None
        for inv in invs:
            days = days_between(inv["dueDate"], t) if inv["dueDate"] < t else 0
            buckets[_bucket_of(days)] += balance_of(inv)
            max_days = max(max_days, days)
            if not oldest_due or inv["dueDate"] < oldest_due:
                oldest_due = inv["dueDate"]
        buckets = {k: round2(v) for k, v in buckets.items()}
        outstanding = round2(total(balance_of(i) for i in invs))
        overdue = round2(outstanding - buckets["current"])
        if overdue_only and overdue <= 0:
            continue
        credit_used = round3(outstanding / c["creditLimit"]) if c["creditLimit"] > 0 else 0
        days_list = pay_days.get(client_id)
        avg_days = js_round(total(days_list) / len(days_list)) if days_list else None

        def slow_payer(limit: int) -> bool:
            return avg_days is not None and avg_days > limit

        if c["status"] == "blocked" or (c["creditLimit"] > 0 and outstanding > c["creditLimit"]) or max_days > 60 or (slow_payer(60) and overdue > 0):
            risk = "high"
        elif credit_used > 0.8 or max_days > 30 or client_id in open_reminder or slow_payer(45):
            risk = "watch"
        else:
            risk = "ok"
        lp = last_payment.get(client_id)
        rows.append({
            "clientId": client_id,
            "clientName": c["name"],
            "clientCode": c["code"],
            "status": c["status"],
            "salesRep": c["salesRep"],
            "zone": c["zone"],
            "tags": c.get("tags") or [],
            "paymentTermsDays": c["paymentTermsDays"],
            "creditLimit": c["creditLimit"],
            "outstanding": outstanding,
            "overdue": overdue,
            "creditUsedPct": credit_used,
            "buckets": buckets,
            "openInvoices": len(invs),
            **({"oldestDueDate": oldest_due} if oldest_due else {}),
            "maxDaysOverdue": max_days,
            **({"lastPaymentAt": lp["at"], "lastPaymentAmount": lp["amount"]} if lp else {}),
            **({"avgDaysToPay": avg_days} if avg_days is not None else {}),
            "openDisputes": disputes.get(client_id, 0),
            **({"lastReminderAt": last_reminder[client_id]} if client_id in last_reminder else {}),
            "risk": risk,
        })  # fmt: skip
    rows = sort_by(rows, lambda a, b: cmp(b["overdue"], a["overdue"]) or cmp(b["outstanding"], a["outstanding"]))

    totals: Doc = {**{k: 0.0 for k in BUCKETS}, "outstanding": 0.0, "overdue": 0.0, "clients": len(rows), "clientsOverdue": 0, "dso": 0}
    for r in rows:
        for k in BUCKETS:
            totals[k] += r["buckets"][k]
        totals["outstanding"] += r["outstanding"]
        totals["overdue"] += r["overdue"]
        if r["overdue"] > 0:
            totals["clientsOverdue"] += 1
    for k in [*BUCKETS, "outstanding", "overdue"]:
        totals[k] = round2(totals[k])
    # DSO over the same client scope as the rows' filter (matching clients' invoices of the last 90 days).
    revenue90 = total(
        i["totalTtc"]
        for i in crud.invoices.all()
        if i["status"] not in ("cancelled", "draft") and from90 <= i["issuedAt"] <= t
        and crud.clients.get(i["clientId"]) and matches(crud.clients.get(i["clientId"]))
    )  # fmt: skip
    totals["dso"] = js_round(totals["outstanding"] / revenue90 * 90) if revenue90 > 0 else 0
    return {"asOf": t, "totals": totals, "rows": rows}
