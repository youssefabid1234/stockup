"""Clients: summaries with financial KPIs, detail, "the usual" basket, create/update/notes."""

from __future__ import annotations

from itertools import islice

from app import crud
from app.core.activity import Ctx, log_event, now, today
from app.core.db import Doc, per_data_version, transactional
from app.core.listing import Key, ListQuery, apply_sort, count_by, respond, sort_rows, split_set
from app.core.utils import add_days, cmp, collate_key, js_number, normalize, round2, round3, sort_by, to_date, weekday_of
from app.services import client_events, invoices, orders, payments
from app.services.tags import check_tags, tag_label


def is_sale(order: Doc) -> bool:
    """Orders that count as sales (revenue, usual basket…)."""
    return order["status"] not in ("draft", "cancelled")


def next_delivery_date(client: Doc) -> str:
    """Next date strictly after today that is one of the client's delivery days (tomorrow if none set)."""
    t = today()
    days = client.get("deliveryDays") or []
    for i in range(1, 8):
        d = add_days(t, i)
        if days and weekday_of(d) in days:
            return d
    return add_days(t, 1)


def client_balances(client_id: str) -> Doc:
    """Outstanding € TTC (unpaid balance of open invoices) and the overdue part of it."""
    a = _agg(client_id)
    return {"outstanding": a["outstanding"], "overdue": a["overdue"]}


@per_data_version
def _aggregates() -> dict[str, Doc]:
    """Per client: outstanding / overdue € TTC, last order date, 30-day revenue, open issues.
    One pass over orders and invoices, cached until the next write."""
    t = today()
    from30 = add_days(t, -30)
    agg: dict[str, Doc] = {}

    def a_of(client_id: str) -> Doc:
        a = agg.get(client_id)
        if a is None:
            a = agg[client_id] = {"outstanding": 0.0, "overdue": 0.0, "last": None, "rev": 0.0}
        return a

    for inv in crud.invoices.rows.values():
        if not invoices.is_open(inv):
            continue
        a = a_of(inv["clientId"])
        a["outstanding"] += invoices.balance_of(inv)
        if inv["dueDate"] < t:
            a["overdue"] += invoices.balance_of(inv)
    for o in crud.orders.rows.values():
        if not is_sale(o):
            continue
        a = a_of(o["clientId"])
        d = to_date(o["createdAt"])
        if not a["last"] or d > a["last"]:
            a["last"] = d
        if from30 < o["deliveryDate"] <= t:
            a["rev"] += o["totalHt"]
    open_issues = client_events.open_issues_by_client()
    return {
        cid: {
            "openIssues": open_issues.get(cid, 0),
            "outstanding": round2(a["outstanding"]),
            "overdue": round2(a["overdue"]),
            **({"lastOrderAt": a["last"]} if a["last"] else {}),
            "revenue30d": round2(a["rev"]),
        }
        for cid, a in agg.items()
    } | {cid: {"openIssues": n, "outstanding": 0, "overdue": 0, "revenue30d": 0} for cid, n in open_issues.items() if cid not in agg}


_EMPTY_AGG: Doc = {"openIssues": 0, "outstanding": 0, "overdue": 0, "revenue30d": 0}


def _agg(client_id: str) -> Doc:
    return _aggregates().get(client_id, _EMPTY_AGG)


def _summary(c: Doc) -> Doc:
    return {**c, **_agg(c["id"])}


CLIENT_SORTS: dict[str, Key] = {
    "name": lambda c: collate_key(c["name"]),
    "code": lambda c: c["code"],
    "type": lambda c: c["type"],
    "tags": lambda c: ",".join(c.get("tags") or []),
    "zone": lambda c: collate_key(c["zone"]) if c.get("zone") else None,
    "rep": lambda c: collate_key(c["salesRep"]) if c.get("salesRep") else None,
    "city": lambda c: collate_key(c["city"]) if c.get("city") else None,
    "outstanding": lambda c: _agg(c["id"])["outstanding"],
    "overdue": lambda c: _agg(c["id"])["overdue"],
    "last": lambda c: _agg(c["id"]).get("lastOrderAt"),
    "revenue30d": lambda c: _agg(c["id"])["revenue30d"],
    "status": lambda c: c["status"],
}


def list_clients(lq: ListQuery | None = None, q: str | None = None, type: str | None = None, zone: str | None = None,
                 status: str | None = None, tag: str | None = None) -> list[Doc] | Doc:  # fmt: skip
    """GET /api/clients — by name. Envelope extras: counts per status (ignoring `status`),
    facets.zone / facets.salesRep (every value in the table, for the filter menus)."""
    lq = lq or ListQuery()
    nq = normalize(q) if q else None
    types, zones, statuses = split_set(type), split_set(zone), split_set(status)

    def keep(c: Doc) -> bool:
        if types and c["type"] not in types or zones and c["zone"] not in zones or tag and tag not in (c.get("tags") or []):
            return False
        if nq:
            contacts = " ".join(x["name"] for x in c["contacts"])
            return nq in normalize(f"{c['name']} {c['code']} {c['city']} {contacts}")
        return True

    base = sort_rows(crud.clients.filter(keep), CLIENT_SORTS["name"])
    rows = [c for c in base if c["status"] in statuses] if statuses else base
    rows = apply_sort(rows, lq, CLIENT_SORTS)
    every = crud.clients.rows.values()
    return respond(rows, lq, _summary, lambda: {
        "counts": count_by(base, lambda c: c["status"]),
        "facets": {
            "zone": sorted({c["zone"] for c in every if c.get("zone")}, key=collate_key),
            "salesRep": sorted({c["salesRep"] for c in every if c.get("salesRep")}, key=collate_key),
        },
    })


def client_summary(id: str) -> Doc:
    return _summary(crud.clients.require(id))


def client_detail(id: str) -> Doc:
    summary = client_summary(id)
    prices = []
    for cp in crud.client_prices.filter(lambda cp: cp["clientId"] == id):
        p = crud.products.get(cp["productId"])
        prices.append({"productId": cp["productId"], "productName": p["name"] if p else "?", "price": cp["price"], "listPrice": p["price"] if p else 0})
    recent = list(islice((o for o in orders.orders_newest_first() if o["clientId"] == id), 20))
    open_invoices = sorted(crud.invoices.filter(lambda i: i["clientId"] == id and invoices.is_open(i)), key=lambda i: i["dueDate"])
    return {
        **summary,
        "prices": prices,
        "recentOrders": [orders.order_summary(o) for o in recent],
        "openInvoices": [invoices.invoice_summary(i) for i in open_invoices[:100]],
        "openInvoiceCount": len(open_invoices),
        "payments": payments.list_payments(ListQuery(limit=20), client_id=id),
        "usual": usual_basket(id),
        **client_events.client_history(id),
    }


def usual_basket_of(documents: list[Doc], date_of) -> list[Doc]:
    """Shared "usual basket" algorithm (clients and suppliers): products present in the documents
    (oldest first), with how often (share of documents) and how much. Kept when present in ≥ 25 %
    of them (or the top 5 if fewer than 3 products qualify)."""
    if not documents:
        return []
    stats: dict[str, Doc] = {}
    for doc in documents:
        per_doc: dict[str, float] = {}
        for l in doc["lines"]:
            per_doc[l["productId"]] = per_doc.get(l["productId"], 0) + l["qty"]
        for pid, qty in per_doc.items():
            s = stats.setdefault(pid, {"n": 0, "total": 0, "lastQty": 0, "last": ""})
            s["n"] += 1
            s["total"] += qty
            s["lastQty"] = qty
            s["last"] = date_of(doc)
    lines = []
    for pid, s in stats.items():
        p = crud.products.get(pid)
        lines.append({
            "productId": pid,
            "productName": p["name"] if p else "?",
            "unit": p["unit"] if p else "",
            "avgQty": round3(s["total"] / s["n"]),
            "frequency": round2(s["n"] / len(documents)),
            "lastQty": s["lastQty"],
            "lastOrderedAt": s["last"],
        })  # fmt: skip
    lines = sort_by(lines, lambda a, b: cmp(b["frequency"], a["frequency"]) or cmp(b["lastOrderedAt"], a["lastOrderedAt"]))
    frequent = [l for l in lines if l["frequency"] >= 0.25]
    return frequent if len(frequent) >= 3 else lines[:5]


def usual_basket(client_id: str) -> list[Doc]:
    """"The usual": products this client ordered in the last 60 days."""
    crud.clients.require(client_id)
    since = add_days(today(), -60)
    recent = crud.orders.filter(lambda o: o["clientId"] == client_id and is_sale(o) and o["deliveryDate"] >= since)
    recent = sort_by(recent, lambda a, b: cmp(a["deliveryDate"], b["deliveryDate"]))
    return usual_basket_of(recent, lambda o: o["deliveryDate"])


# ───────── Writes ─────────


def _next_client_code() -> str:
    best = 0
    for c in crud.clients.rows.values():
        n = js_number("".join(ch for ch in c["code"] if ch.isdigit()))
        if n > best:
            best = int(n)
    return f"C{best + 1:04d}"


@transactional
def create_client(ctx: Ctx, input: Doc) -> Doc:
    client = {
        "id": crud.clients.next_id("cli_", 4),
        "code": _next_client_code(),
        "name": input["name"],
        "type": input["type"],
        "contacts": input.get("contacts", []),
        "address": input.get("address", ""),
        "city": input.get("city", ""),
        "zone": input.get("zone", ""),
        "deliveryDays": input.get("deliveryDays", ["mon", "tue", "wed", "thu", "fri"]),
        "paymentTermsDays": input.get("paymentTermsDays", 30),
        "creditLimit": input.get("creditLimit", 2000),
        "status": input.get("status", "prospect"),
        "salesRep": input.get("salesRep", ""),
        "preferences": input.get("preferences", ""),
        "notes": [],
        "createdAt": now(),
        **({"tags": input["tags"]} if input.get("tags") else {}),
    }
    check_tags("client", input.get("tags"))
    crud.clients.put(client)
    log_event(ctx, "client.created", "client", client["id"], f"Nouveau client {client['name']} ({client['code']})")
    return client


@transactional
def update_client(ctx: Ctx, id: str, patch: Doc) -> Doc:
    client = crud.clients.require(id)
    check_tags("client", patch.get("tags"), client.get("tags"))
    updated = crud.clients.put({**client, **patch})
    summary = f"Fiche client {client['name']} modifiée ({', '.join(patch)})"
    if "tags" in patch and len(patch) == 1:
        summary = f"Groupes de {client['name']} : {', '.join(tag_label('client', t) for t in patch['tags']) or 'aucun'}"
    if patch.get("status") and patch["status"] != client["status"]:
        summary = f"Client {client['name']} bloqué" if patch["status"] == "blocked" else f"Client {client['name']} passé en {patch['status']}"
    log_event(ctx, "client.updated", "client", id, summary)
    return updated


@transactional
def add_client_note(ctx: Ctx, id: str, text: str, author: str) -> Doc:
    client = crud.clients.require(id)
    updated = crud.clients.put({**client, "notes": [*client["notes"], {"at": now(), "author": author, "text": text}]})
    log_event(ctx, "client.note_added", "client", id, f"Note ajoutée sur {client['name']} : « {text[:80]} »")
    return updated
