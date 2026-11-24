"""Payments: record and allocate to invoices (oldest open first when allocations are not given)."""

from __future__ import annotations

from app import crud
from app.core.activity import Ctx, log_event, today
from app.core.db import Doc, per_data_version, transactional
from app.core.listing import Key, ListQuery, apply_sort, respond, split_set, sum_of
from app.core.errors import bad_request
from app.core.utils import cmp, collate_key, fmt_eur, normalize, round2, sort_by, total
from app.services import invoices


def payment_summary(p: Doc) -> Doc:
    client = crud.clients.get(p["clientId"])
    allocations = []
    for a in p["allocations"]:
        inv = crud.invoices.get(a["invoiceId"])
        allocations.append({**a, "invoiceNumber": inv["number"]} if inv else a)
    return {**p, "clientName": client["name"] if client else "?", "allocations": allocations}


@per_data_version
def _payments_newest_first() -> list[Doc]:
    return sorted(crud.payments.rows.values(), key=lambda p: p["receivedAt"], reverse=True)


@per_data_version
def payments_by_invoice() -> dict[str, list[Doc]]:
    """invoiceId → payments allocated to it (newest first)."""
    out: dict[str, list[Doc]] = {}
    for p in _payments_newest_first():
        for a in p["allocations"]:
            lst = out.setdefault(a["invoiceId"], [])
            if not lst or lst[-1] is not p:
                lst.append(p)
    return out


def _client_name(client_id: str) -> str:
    c = crud.clients.get(client_id)
    return c["name"] if c else "?"


PAYMENT_SORTS: dict[str, Key] = {
    "date": lambda p: p["receivedAt"],
    "client": lambda p: collate_key(_client_name(p["clientId"])),
    "method": lambda p: p["method"],
    "ref": lambda p: p.get("reference"),
    "amount": lambda p: p["amount"],
}


def list_payments(lq: ListQuery | None = None, client_id: str | None = None, method: str | None = None,
                  q: str | None = None) -> list[Doc] | Doc:  # fmt: skip
    """GET /api/payments — newest first. q = client name, reference or allocated invoice number.
    Envelope extras: sums.amount."""
    lq = lq or ListQuery()
    methods = split_set(method)
    nq = normalize(q) if q else None

    def matches_q(p: Doc) -> bool:
        numbers = " ".join(crud.invoices.rows[a["invoiceId"]]["number"] for a in p["allocations"] if a["invoiceId"] in crud.invoices.rows)
        return nq in normalize(f"{_client_name(p['clientId'])} {p.get('reference') or ''} {numbers}")  # type: ignore[operator]

    rows = [
        p for p in _payments_newest_first()
        if (not client_id or p["clientId"] == client_id) and (not methods or p["method"] in methods) and (not nq or matches_q(p))
    ]  # fmt: skip
    rows = apply_sort(rows, lq, PAYMENT_SORTS)
    return respond(rows, lq, payment_summary, lambda: {"sums": sum_of(rows, amount=lambda p: p["amount"])})


@transactional
def record_payment(ctx: Ctx, input: Doc) -> Doc:
    client = crud.clients.require(input["clientId"])
    if not input["amount"] > 0:
        raise bad_request("invalid_amount", "Le montant doit être positif")
    amount = round2(input["amount"])

    allocations: list[Doc] = []
    if input.get("allocations"):
        # Explicit allocations: each must target an invoice of this client and fit its balance.
        if round2(total(a["amount"] for a in input["allocations"])) > amount:
            raise bad_request("over_allocated", "La somme des affectations dépasse le montant du paiement")
        for a in input["allocations"]:
            inv = crud.invoices.require(a["invoiceId"])
            if inv["clientId"] != client["id"]:
                raise bad_request("wrong_client", f"La facture {inv['number']} n'appartient pas à {client['name']}")
            if round2(a["amount"]) > invoices.balance_of(inv):
                raise bad_request("over_allocated", f"Montant supérieur au solde de {inv['number']} ({fmt_eur(invoices.balance_of(inv))})")
            allocations.append({"invoiceId": inv["id"], "amount": round2(a["amount"])})
    else:
        # Auto: settle the oldest open invoices first. Any remainder stays as unallocated credit.
        left = amount
        open_invoices = crud.invoices.filter(lambda i: i["clientId"] == client["id"] and invoices.is_open(i))
        open_invoices = sort_by(open_invoices, lambda a, b: cmp(a["issuedAt"], b["issuedAt"]) or cmp(a["dueDate"], b["dueDate"]))
        for inv in open_invoices:
            if left <= 0:
                break
            take = round2(min(left, invoices.balance_of(inv)))
            allocations.append({"invoiceId": inv["id"], "amount": take})
            left = round2(left - take)

    for a in allocations:
        inv = crud.invoices.require(a["invoiceId"])
        updated = {**inv, "amountPaid": round2(inv["amountPaid"] + a["amount"])}
        crud.invoices.put({**updated, "status": invoices.paid_status(updated)})

    payment = {
        "id": crud.payments.next_id("pay_"),
        "clientId": client["id"],
        "amount": amount,
        "method": input["method"],
        "receivedAt": input.get("receivedAt") or today(),
        **({"reference": input["reference"]} if input.get("reference") else {}),
        "allocations": allocations,
    }
    crud.payments.put(payment)
    numbers = [crud.invoices.require(a["invoiceId"])["number"] for a in allocations]
    where = f" (affecté à {', '.join(numbers)})" if numbers else " (non affecté)"
    log_event(ctx, "payment.recorded", "payment", payment["id"], f"Paiement de {fmt_eur(amount)} reçu de {client['name']}{where}")
    return payment_summary(payment)
