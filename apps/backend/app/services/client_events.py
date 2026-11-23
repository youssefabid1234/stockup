"""Client history: the long-term relationship log of each client (complaints, returns, disputes,
calls, visits, negotiations…), possibly spanning years. Read by the client page and by the agents
("what should I know before talking to this client?"); written when something happens (e.g. the
voice agent records a complaint during a call).

Issue types (complaint, return, dispute…) are created with status "open" and resolved later;
other types (call, visit, note…) have no status.
"""

from __future__ import annotations

from typing import Callable

from app import crud
from app.core.activity import Ctx, log_event, now, today
from app.core.db import Doc, transactional
from app.core.listing import Key, ListQuery, apply_sort, count_by, respond, split_set, sum_of
from app.core.errors import bad_request
from app.core.utils import add_days, cmp, compact, normalize, to_date

# Types that are "issues": they start open and are resolved later.
ISSUE_TYPES = {"complaint", "quality_issue", "delivery_issue", "return", "dispute", "late_payment", "churn_risk"}
# Counted in eventStats.complaints12m.
COMPLAINT_TYPES = {"complaint", "quality_issue", "delivery_issue"}

EVENT_TYPE_LABEL = {
    "onboarding": "Entrée en relation",
    "call": "Appel",
    "visit": "Visite",
    "complaint": "Réclamation",
    "quality_issue": "Problème qualité",
    "delivery_issue": "Problème de livraison",
    "return": "Retour marchandise",
    "credit_note": "Avoir",
    "dispute": "Litige",
    "late_payment": "Incident de paiement",
    "payment_plan": "Échéancier",
    "price_negotiation": "Négociation tarifaire",
    "special_request": "Demande spéciale",
    "menu_change": "Changement de carte",
    "contact_change": "Changement de contact",
    "compliment": "Compliment",
    "churn_risk": "Risque de perte",
    "won_back": "Client reconquis",
    "note": "Note",
}

# Default author of an event, by actor.
ACTOR_AUTHOR = {"user": "Équipe", "ai_chat": "Assistant IA", "voice_agent": "Agent vocal", "system": "Système"}


def newest_first(a: Doc, b: Doc) -> int:
    """Newest first (ties: highest id first)."""
    return cmp(b["at"], a["at"]) or cmp(b["id"], a["id"])


def filter_history(events: list[Doc], owner_key: str, owner_id: str | None = None, type: str | None = None,
                   status: str | None = None, q: str | None = None, date_from: str | None = None,
                   date_to: str | None = None, limit: int | None = None) -> list[Doc]:  # fmt: skip
    """Shared filter of client AND supplier events: type (comma list), status, full text q
    (every word in title + description, accent-insensitive), from/to dates (inclusive), limit. Newest first."""
    types = split_set(type)
    q_tokens = [t for t in normalize(q).split(" ") if t] if q else []

    def keep(e: Doc) -> bool:
        if owner_id and e[owner_key] != owner_id:
            return False
        if types and e["type"] not in types:
            return False
        if status and e.get("status") != status:
            return False
        d = to_date(e["at"])
        if (date_from and d < date_from) or (date_to and d > date_to):
            return False
        if q_tokens:
            text = normalize(f"{e['title']} {e['description']}")
            if not all(t in text for t in q_tokens):
                return False
        return True

    out = sorted((e for e in events if keep(e)), key=lambda e: (e["at"], e["id"]), reverse=True)
    return out[:limit] if limit else out


EVENT_SORTS: dict[str, Key] = {
    "at": lambda e: e["at"],
    "type": lambda e: e["type"],
    "status": lambda e: e.get("status"),
    "amount": lambda e: e.get("amount"),
    # open issues first, then the rest; each newest first (apply on a newest-first list, order=asc)
    "open": lambda e: 0 if e.get("status") == "open" else 1,
}


def page_history(events: list[Doc], lq: ListQuery, owner_key: str, owner_id: str | None, view, **filters) -> list[Doc] | Doc:
    """A page of history (client or supplier events). Envelope extras: counts per status (ignoring `status`),
    countsByType and sums.amount over the filtered rows."""
    status = filters.pop("status", None)
    base = filter_history(events, owner_key, owner_id, **filters)
    rows = [e for e in base if e.get("status") == status] if status else base
    rows = apply_sort(rows, lq, EVENT_SORTS)
    return respond(rows, lq, view, lambda: {
        "counts": count_by(base, lambda e: e.get("status")),
        "countsByType": count_by(rows, lambda e: e["type"]),
        "sums": sum_of(rows, amount=lambda e: e.get("amount") or 0),
    })


def event_summary(e: Doc) -> Doc:
    client = crud.clients.get(e["clientId"])
    order = crud.orders.get(e["orderId"]) if e.get("orderId") else None
    invoice = crud.invoices.get(e["invoiceId"]) if e.get("invoiceId") else None
    return {
        **e,
        "clientName": client["name"] if client else "?",
        **({"orderNumber": order["number"]} if order else {}),
        **({"invoiceNumber": invoice["number"]} if invoice else {}),
    }


def list_client_events(lq: ListQuery, client_id: str, **filters) -> list[Doc] | Doc:
    """GET /api/clients/:id/events — history of one client, newest first."""
    crud.clients.require(client_id)
    return page_history(crud.client_events.all(), lq, "clientId", client_id, event_summary, **filters)


def search_client_events(lq: ListQuery, client_id: str | None = None, **filters) -> list[Doc] | Doc:
    """GET /api/client-events — all clients, newest first, with the client name."""
    return page_history(crud.client_events.all(), lq, "clientId", client_id, event_summary, **filters)


def open_issues_by_client() -> dict[str, int]:
    out: dict[str, int] = {}
    for e in crud.client_events.rows.values():
        if e.get("status") == "open":
            out[e["clientId"]] = out.get(e["clientId"], 0) + 1
    return out


def client_history(client_id: str) -> Doc:
    """recentEvents (latest 10) + eventStats for the client page."""
    events = filter_history(crud.client_events.all(), "clientId", client_id)
    from12m = add_days(today(), -365)
    open_count = complaints = returns = 0
    for e in events:
        if e.get("status") == "open":
            open_count += 1
        if to_date(e["at"]) < from12m:
            continue
        if e["type"] in COMPLAINT_TYPES:
            complaints += 1
        if e["type"] == "return":
            returns += 1
    stats = {"total": len(events), "open": open_count, "complaints12m": complaints, "returns12m": returns}
    if events:
        stats["since"] = to_date(events[-1]["at"])
    return {"recentEvents": [event_summary(e) for e in events[:10]], "eventStats": stats}


# ───────── Writes (shared with supplier events) ─────────


def event_at(at: str | None) -> str:
    """Given timestamp, a bare date (→ 09:00), or now."""
    if not at:
        return now()
    return f"{at}T09:00:00.000Z" if len(at) == 10 else at


def apply_patch(table, id: str, patch: Doc, check: Callable[[Doc, Doc], None]) -> tuple[Doc, Doc, bool]:
    """Shared update of a client/supplier event. Resolving sets resolvedAt, reopening clears it.
    Returns (before, after, resolving)."""
    ev = table.require(id)
    check(ev, patch)
    resolving = patch.get("status") == "resolved" and ev.get("status") != "resolved"
    updated = compact({**ev, **patch})
    if resolving:
        updated["resolvedAt"] = now()
    if patch.get("status") == "open":
        updated.pop("resolvedAt", None)  # reopened
    table.put(updated)
    return ev, updated, resolving


def _check_links(client_id: str, input: Doc) -> None:
    if input.get("orderId"):
        o = crud.orders.require(input["orderId"])
        if o["clientId"] != client_id:
            raise bad_request("order_mismatch", f"La commande {o['number']} n'appartient pas à ce client")
    if input.get("invoiceId"):
        i = crud.invoices.require(input["invoiceId"])
        if i["clientId"] != client_id:
            raise bad_request("invoice_mismatch", f"La facture {i['number']} n'appartient pas à ce client")
    for pid in input.get("productIds") or []:
        crud.products.require(pid)


@transactional
def create_client_event(ctx: Ctx, client_id: str, input: Doc) -> Doc:
    client = crud.clients.require(client_id)
    _check_links(client_id, input)
    status = input.get("status") or ("open" if input["type"] in ISSUE_TYPES else None)
    ev = compact({
        "id": crud.client_events.next_id("cev_"),
        "clientId": client_id,
        "at": event_at(input.get("at")),
        "type": input["type"],
        "title": input["title"],
        "description": input.get("description", ""),
        "channel": input.get("channel") or ("voice_agent" if ctx.actor == "voice_agent" else None),
        "author": input.get("author") or ctx.actor_name or ACTOR_AUTHOR[ctx.actor],
        "severity": input.get("severity"),
        "status": status,
        "resolvedAt": now() if status == "resolved" else None,
        "orderId": input.get("orderId"),
        "invoiceId": input.get("invoiceId"),
        "productIds": input.get("productIds"),
        "amount": input.get("amount"),
        "tags": input.get("tags"),
    })  # fmt: skip
    crud.client_events.put(ev)
    log_event(ctx, "client_event.created", "client", client_id,
              f"{EVENT_TYPE_LABEL[ev['type']]} enregistré(e) pour {client['name']} : « {ev['title']} »")  # fmt: skip
    return ev


@transactional
def update_client_event(ctx: Ctx, id: str, patch: Doc) -> Doc:
    ev = crud.client_events.require(id)
    client = crud.clients.require(ev["clientId"])
    _, updated, resolving = apply_patch(crud.client_events, id, patch, lambda e, p: _check_links(e["clientId"], p))
    if resolving:
        how = f" — {updated['resolution'][:80]}" if updated.get("resolution") else ""
        log_event(ctx, "client_event.resolved", "client", ev["clientId"],
                  f"{EVENT_TYPE_LABEL[updated['type']]} résolu(e) pour {client['name']} : « {updated['title']} »{how}")  # fmt: skip
    else:
        log_event(ctx, "client_event.updated", "client", ev["clientId"],
                  f"Historique de {client['name']} modifié : « {updated['title']} » ({', '.join(patch)})")  # fmt: skip
    return updated
