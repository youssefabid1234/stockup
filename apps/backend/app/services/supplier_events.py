"""Supplier history: the long-term relationship log of each supplier (quality issues, shortages,
price changes, disputes, visits…). Same model as client history (see client_events.py)."""

from __future__ import annotations

from app import crud
from app.core.activity import Ctx, log_event, now, today
from app.core.db import Doc, transactional
from app.core.errors import bad_request
from app.core.utils import add_days, compact, to_date
from app.core.listing import ListQuery
from app.services.client_events import ACTOR_AUTHOR, apply_patch, event_at, filter_history, page_history

# Types that are "issues": they start open and are resolved later. Counted in eventStats.issues12m.
SUPPLIER_ISSUE_TYPES = {"quality_issue", "delivery_issue", "shortage", "return", "dispute", "invoice_issue"}

SUPPLIER_EVENT_TYPE_LABEL = {
    "onboarding": "Référencement",
    "call": "Appel",
    "visit": "Visite",
    "quality_issue": "Problème qualité",
    "delivery_issue": "Problème de livraison",
    "shortage": "Rupture d'approvisionnement",
    "return": "Retour fournisseur",
    "credit_note": "Avoir",
    "dispute": "Litige",
    "price_change": "Changement de prix",
    "price_negotiation": "Négociation tarifaire",
    "invoice_issue": "Problème de facture",
    "payment": "Incident de paiement",
    "contract": "Contrat",
    "certification": "Certification",
    "contact_change": "Changement de contact",
    "compliment": "Compliment",
    "note": "Note",
}


def supplier_event_summary(e: Doc) -> Doc:
    supplier = crud.suppliers.get(e["supplierId"])
    po = crud.purchase_orders.get(e["purchaseOrderId"]) if e.get("purchaseOrderId") else None
    return {**e, "supplierName": supplier["name"] if supplier else "?", **({"poNumber": po["number"]} if po else {})}


def list_supplier_events(lq: ListQuery, supplier_id: str, **filters) -> list[Doc] | Doc:
    """GET /api/suppliers/:id/events"""
    crud.suppliers.require(supplier_id)
    return page_history(crud.supplier_events.all(), lq, "supplierId", supplier_id, supplier_event_summary, **filters)


def search_supplier_events(lq: ListQuery, supplier_id: str | None = None, **filters) -> list[Doc] | Doc:
    """GET /api/supplier-events"""
    return page_history(crud.supplier_events.all(), lq, "supplierId", supplier_id, supplier_event_summary, **filters)


def supplier_history(supplier_id: str) -> Doc:
    """openIssues + recentEvents (latest 10) + eventStats for the supplier page."""
    events = filter_history(crud.supplier_events.all(), "supplierId", supplier_id)
    from12m = add_days(today(), -365)
    open_count = sum(1 for e in events if e.get("status") == "open")
    issues = sum(1 for e in events if to_date(e["at"]) >= from12m and e["type"] in SUPPLIER_ISSUE_TYPES)
    stats = {"total": len(events), "open": open_count, "issues12m": issues}
    if events:
        stats["since"] = to_date(events[-1]["at"])
    return {"openIssues": open_count, "recentEvents": [supplier_event_summary(e) for e in events[:10]], "eventStats": stats}


def _check_links(supplier_id: str, input: Doc) -> None:
    if input.get("purchaseOrderId"):
        po = crud.purchase_orders.require(input["purchaseOrderId"])
        if po["supplierId"] != supplier_id:
            raise bad_request("purchase_order_mismatch", f"La commande {po['number']} n'appartient pas à ce fournisseur")
    for pid in input.get("productIds") or []:
        crud.products.require(pid)


@transactional
def create_supplier_event(ctx: Ctx, supplier_id: str, input: Doc) -> Doc:
    supplier = crud.suppliers.require(supplier_id)
    _check_links(supplier_id, input)
    status = input.get("status") or ("open" if input["type"] in SUPPLIER_ISSUE_TYPES else None)
    ev = compact({
        "id": crud.supplier_events.next_id("sev_"),
        "supplierId": supplier_id,
        "at": event_at(input.get("at")),
        "type": input["type"],
        "title": input["title"],
        "description": input.get("description", ""),
        "channel": input.get("channel") or ("voice_agent" if ctx.actor == "voice_agent" else None),
        "author": input.get("author") or ctx.actor_name or ACTOR_AUTHOR[ctx.actor],
        "severity": input.get("severity"),
        "status": status,
        "resolvedAt": now() if status == "resolved" else None,
        "purchaseOrderId": input.get("purchaseOrderId"),
        "productIds": input.get("productIds"),
        "amount": input.get("amount"),
        "tags": input.get("tags"),
    })  # fmt: skip
    crud.supplier_events.put(ev)
    log_event(ctx, "supplier_event.created", "supplier", supplier_id,
              f"{SUPPLIER_EVENT_TYPE_LABEL[ev['type']]} enregistré(e) pour le fournisseur {supplier['name']} : « {ev['title']} »")  # fmt: skip
    return ev


@transactional
def update_supplier_event(ctx: Ctx, id: str, patch: Doc) -> Doc:
    ev = crud.supplier_events.require(id)
    supplier = crud.suppliers.require(ev["supplierId"])
    _, updated, resolving = apply_patch(crud.supplier_events, id, patch, lambda e, p: _check_links(e["supplierId"], p))
    label = SUPPLIER_EVENT_TYPE_LABEL[updated["type"]]
    if resolving:
        how = f" — {updated['resolution'][:80]}" if updated.get("resolution") else ""
        log_event(ctx, "supplier_event.resolved", "supplier", ev["supplierId"],
                  f"{label} résolu(e) pour le fournisseur {supplier['name']} : « {updated['title']} »{how}")  # fmt: skip
    else:
        log_event(ctx, "supplier_event.updated", "supplier", ev["supplierId"],
                  f"Historique du fournisseur {supplier['name']} modifié : « {updated['title']} » ({', '.join(patch)})")  # fmt: skip
    return updated
