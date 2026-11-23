"""
Relationship history tools: read a client's / supplier's long-term history (complaints, returns,
disputes, calls, visits…) and record a new event during a call (e.g. a complaint).
"""

from typing import Literal

from pydantic import Field

from .erp import enc
from .registry import ToolContext, tool


def compact_event(e: dict) -> dict:
    """One compact line per event, for the model."""
    description = e.get("description")
    return {
        "id": e["id"],
        "date": e["at"][:10],
        "type": e["type"],
        "title": e["title"],
        **({"description": f"{description[:200]}…" if len(description) > 200 else description} if description else {}),
        **{k: e[k] for k in ("status", "severity", "resolution") if e.get(k)},
        **({"amount": e["amount"]} if e.get("amount") is not None else {}),
        "author": e.get("author"),
    }


def open_first(events: list[dict]) -> list[dict]:
    """Open issues first, then the rest (the API already returns newest first)."""
    return [e for e in events if e.get("status") == "open"] + [e for e in events if e.get("status") != "open"]


Severity = Literal["low", "medium", "high"]
LIMIT = Field(None, description="Nombre max d'événements (défaut 20)")

# ── Clients ──

CLIENT_TYPES = (
    "complaint, quality_issue, delivery_issue, return, credit_note, dispute, late_payment, payment_plan, price_negotiation, "
    "special_request, menu_change, contact_change, compliment, churn_risk, won_back, call, visit, onboarding, note"
)
ClientEventType = Literal[
    "complaint", "quality_issue", "delivery_issue", "return", "dispute", "late_payment", "special_request",
    "price_negotiation", "menu_change", "contact_change", "compliment", "churn_risk", "call", "note",
]  # fmt: skip


@tool
async def get_client_history(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0012"),
    types: list[str] | None = Field(None, description=f"Optionnel : filtrer par type ({CLIENT_TYPES})"),
    limit: float | None = LIMIT,
) -> list[dict]:
    """
    Historique de la relation avec un client (peut couvrir des années) : réclamations, retours, litiges, retards de paiement, appels, visites…
    Problèmes ouverts en premier, puis du plus récent au plus ancien. À consulter avant de parler à un client mécontent ou pour savoir « ce qui s'est passé ».
    Client relationship history, open issues first.
    """
    n = min(int(limit or 20), 500)
    # sort=open: open issues first, then newest first; only the first n come back (the API pages its lists).
    events = await ctx.erp.get(f"/api/clients/{enc(client_id)}/events", {"type": ",".join(types) if types else None, "sort": "open", "limit": n})
    return [compact_event(e) for e in open_first(events)[:n]]


@tool
async def log_client_event(
    ctx: ToolContext,
    client_id: str,
    type: ClientEventType,
    title: str = Field(description="Ligne courte en français, ex. « Réclamation : colis abîmé à la livraison »"),
    description: str | None = Field(None, description="Ce qui s'est passé, en français, peut citer le client"),
    severity: Severity | None = None,
    order_id: str | None = Field(None, description="Optionnel : commande concernée (ord_…)"),
) -> dict:
    """
    Enregistre un événement dans l'historique du client, ex. une réclamation pendant l'appel (« le colis est arrivé abîmé »).
    Les réclamations, problèmes qualité/livraison, retours, litiges sont créés « ouverts » pour être traités par l'équipe.
    Reformule fidèlement ce que dit le client, sans promettre de geste commercial. Record a client event (e.g. a complaint).
    """
    body = {"type": type, "title": title, "description": description, "severity": severity, "orderId": order_id}
    event = await ctx.erp.post(f"/api/clients/{enc(client_id)}/events", without_none(body))
    return compact_event(event)


# ── Suppliers ──

SUPPLIER_TYPES = (
    "quality_issue, delivery_issue, shortage, return, credit_note, dispute, price_change, price_negotiation, invoice_issue, "
    "payment, contract, certification, contact_change, compliment, call, visit, onboarding, note"
)
SupplierEventType = Literal[
    "quality_issue", "delivery_issue", "shortage", "return", "dispute", "price_change", "invoice_issue", "call", "note"
]


@tool
async def get_supplier_history(
    ctx: ToolContext,
    supplier_id: str = Field(description="ex. sup_0003"),
    types: list[str] | None = Field(None, description=f"Optionnel : filtrer par type ({SUPPLIER_TYPES})"),
    limit: float | None = LIMIT,
) -> list[dict]:
    """
    Historique de la relation avec un fournisseur : problèmes qualité, retards, ruptures, hausses de prix, litiges, contrats…
    Problèmes ouverts en premier, puis du plus récent au plus ancien. Supplier relationship history, open issues first.
    """
    n = min(int(limit or 20), 500)
    # sort=open: open issues first, then newest first; only the first n come back (the API pages its lists).
    events = await ctx.erp.get(f"/api/suppliers/{enc(supplier_id)}/events", {"type": ",".join(types) if types else None, "sort": "open", "limit": n})
    return [compact_event(e) for e in open_first(events)[:n]]


@tool
async def log_supplier_event(
    ctx: ToolContext,
    supplier_id: str,
    type: SupplierEventType,
    title: str = Field(description="Ligne courte en français, ex. « Produit livré non conforme »"),
    description: str | None = None,
    severity: Severity | None = None,
    purchase_order_id: str | None = Field(None, description="Optionnel : commande fournisseur concernée (po_…)"),
) -> dict:
    """
    Enregistre un événement dans l'historique d'un fournisseur, ex. un lot de mauvaise qualité, une livraison incomplète, une rupture.
    Les problèmes sont créés « ouverts ». Record a supplier event (quality issue, shortage, price change…).
    """
    body = {"type": type, "title": title, "description": description, "severity": severity, "purchaseOrderId": purchase_order_id}
    event = await ctx.erp.post(f"/api/suppliers/{enc(supplier_id)}/events", without_none(body))
    return compact_event(event)


def without_none(d: dict) -> dict:
    """Leave out the optional arguments the model did not give."""
    return {k: v for k, v in d.items() if v is not None}
