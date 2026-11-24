"""Invoices. Stored status is issued | partially_paid | paid | cancelled (| draft).
"overdue" is never stored: it is computed on read (open invoice whose dueDate < today)."""

from __future__ import annotations

from app import crud
from app.core.activity import Ctx, log_event, today
from app.core.db import Doc, per_data_version
from app.core.listing import Key, ListQuery, apply_sort, count_by, respond, split_set, sum_by, sum_of
from app.core.errors import conflict
from app.core.utils import add_days, collate_key, days_between, fmt_eur, normalize, round2, total
from app.services import payments
from app.services.stock import line_qty

OPEN = {"issued", "partially_paid", "overdue"}


def balance_of(inv: Doc) -> float:
    return round2(inv["totalTtc"] - inv["amountPaid"])


def is_open(inv: Doc) -> bool:
    return inv["status"] in OPEN and balance_of(inv) > 0


def effective_status(inv: Doc) -> str:
    """Status as seen by readers, with "overdue" computed against today."""
    if is_open(inv) and inv["dueDate"] < today():
        return "overdue"
    return inv["status"]


def invoice_summary(inv: Doc, with_lines: bool = False) -> Doc:
    """List row (no `lines`, `lineCount` instead); `with_lines` for the detail."""
    status = effective_status(inv)
    client = crud.clients.get(inv["clientId"])
    return {
        **({k: v for k, v in inv.items() if k != "lines"} if not with_lines else inv),
        "lineCount": len(inv["lines"]),
        "status": status,
        "clientName": client["name"] if client else "?",
        "balance": balance_of(inv),
        "daysOverdue": days_between(inv["dueDate"], today()) if status == "overdue" else 0,
    }


@per_data_version
def _invoices_newest_first() -> list[tuple[Doc, str]]:
    """(invoice, effective status), newest issued first (ties: highest number). Cached until the next write."""
    rows = sorted(crud.invoices.rows.values(), key=lambda i: (i["issuedAt"], i["number"]), reverse=True)
    return [(i, effective_status(i)) for i in rows]


def _client_name(client_id: str) -> str:
    c = crud.clients.get(client_id)
    return c["name"] if c else "?"


INVOICE_SORTS: dict[str, Key] = {
    "number": lambda r: r[0]["number"],
    "client": lambda r: collate_key(_client_name(r[0]["clientId"])),
    "issued": lambda r: r[0]["issuedAt"],
    "due": lambda r: r[0]["dueDate"],
    "ttc": lambda r: r[0]["totalTtc"],
    "paid": lambda r: r[0]["amountPaid"],
    "balance": lambda r: balance_of(r[0]),
    "status": lambda r: r[1],
}


def list_invoices(lq: ListQuery, status: str | None = None, client_id: str | None = None, q: str | None = None) -> list[Doc] | Doc:
    """GET /api/invoices — newest first. `status` is a comma list of effective statuses (overdue is computed)
    plus the pseudo-status "open" (any unpaid balance). Envelope extras: counts per status (ignoring `status`),
    sums of the filtered rows (totalTtc, amountPaid, balance), sumsByStatus (balance, totalTtc)."""
    statuses = split_set(status)
    nq = normalize(q) if q else None
    base = [
        r for r in _invoices_newest_first()
        if (not client_id or r[0]["clientId"] == client_id)
        and (not nq or nq in f"{normalize(r[0]['number'])} {normalize(_client_name(r[0]['clientId']))}")
    ]  # fmt: skip

    def keep(r: tuple[Doc, str]) -> bool:
        return r[1] in statuses or ("open" in statuses and r[1] in OPEN and balance_of(r[0]) > 0)  # type: ignore[operator]

    rows = [r for r in base if keep(r)] if statuses else base
    rows = apply_sort(rows, lq, INVOICE_SORTS)
    return respond(rows, lq, lambda r: invoice_summary(r[0]), lambda: {
        "counts": count_by(base, lambda r: r[1]),
        "sums": sum_of(rows, totalTtc=lambda r: r[0]["totalTtc"], amountPaid=lambda r: r[0]["amountPaid"], balance=lambda r: balance_of(r[0])),
        "sumsByStatus": sum_by(base, lambda r: r[1], balance=lambda r: balance_of(r[0]), totalTtc=lambda r: r[0]["totalTtc"]),
    })


def invoice_detail(id: str) -> Doc:
    inv = crud.invoices.require(id)
    return {
        **invoice_summary(inv, with_lines=True),
        "client": crud.clients.require(inv["clientId"]),
        "payments": [payments.payment_summary(p) for p in reversed(payments.payments_by_invoice().get(id, []))],
    }


def paid_status(inv: Doc) -> str:
    """Status after a payment changes amountPaid."""
    if inv["status"] in ("cancelled", "draft"):
        return inv["status"]
    if balance_of(inv) <= 0:
        return "paid"
    return "partially_paid" if inv["amountPaid"] > 0 else "issued"


def invoice_order(ctx: Ctx, order: Doc) -> Doc:
    """Build the invoice of a delivered order: lines from preparedQty ?? qty, VAT per product,
    due date = issue date + client payment terms."""
    if order["status"] != "delivered":
        raise conflict("invalid_transition", f"Seule une commande livrée peut être facturée (statut actuel : {order['status']})")
    client = crud.clients.require(order["clientId"])
    lines = []
    for l in order["lines"]:
        p = crud.products.get(l["productId"])
        qty = line_qty(l)
        lines.append({
            "productId": l["productId"],
            "label": p["name"] if p else l["productId"],
            "qty": qty,
            "unitPrice": l["unitPrice"],
            "vatRate": p["vatRate"] if p else 0.055,
            "totalHt": round2(qty * l["unitPrice"]),
        })  # fmt: skip
    total_ht = round2(total(l["totalHt"] for l in lines))
    total_vat = round2(total(l["totalHt"] * l["vatRate"] for l in lines))
    issued_at = today()
    inv = {
        "id": crud.invoices.next_id("inv_"),
        "number": crud.invoices.next_number("FAC", issued_at[:4]),
        "clientId": client["id"],
        "orderIds": [order["id"]],
        "status": "issued",
        "issuedAt": issued_at,
        "dueDate": add_days(issued_at, client["paymentTermsDays"]),
        "lines": lines,
        "totalHt": total_ht,
        "totalVat": total_vat,
        "totalTtc": round2(total_ht + total_vat),
        "amountPaid": 0,
    }
    crud.invoices.put(inv)
    crud.orders.put({**order, "status": "invoiced", "invoiceId": inv["id"]})
    log_event(ctx, "invoice.issued", "invoice", inv["id"],
              f"Facture {inv['number']} émise pour {client['name']} ({fmt_eur(inv['totalTtc'])} TTC, échéance {inv['dueDate']})")  # fmt: skip
    return inv
