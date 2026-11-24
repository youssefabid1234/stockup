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
LIMIT = Field(None, description="Max number of events (default 20)")

# ── Clients ──

CLIENT_TYPES = (
    "complaint, quality_issue, delivery_issue, return, credit_note, fight, late_payment, payment_plan, price_negotiation, "
    "special_request, menu_change, contact_change, compliments, churn_risk, won_back, call, visit, onboarding, note"
)
ClientEventType = Literal[
    "complaint", "quality_issue", "delivery_issue", "return", "dispute", "late_payment", "special_request",
    "price_negotiation", "menu_change", "contact_change", "compliment", "churn_risk", "call", "note",
]  # fmt: skip


@tool
async def get_client_history(
    ctx: ToolContext,
    client_id: str = Field(description="ex. cli_0012"),
    types: list[str] | None = Field(None, description=f"Optional: Filter by type ({CLIENT_TYPES})"),
    limit: float | None = LIMIT,
) -> list[dict]:
    """
    History of the relationship with a customer (can cover years): claims, returns, disputes, late payment, calls, visits...
    Problems opened first, then from the latest to the oldest. To consult before talking to a discontented client or to know "what happened".
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
    title: str = Field(description="Short line in English, e.g. \"Claim: parcel damaged on delivery\""),
    description: str | None = Field(None, description="What happened in English can be cited as the client"),
    severity: Severity | None = None,
    order_id: str | None = Field(None, description="Optional: command concerned (or_...)"),
) -> dict:
    """Record a customer event in English. Complaints, quality or delivery issues, returns and disputes remain open for follow-up. Record what the caller said without promising compensation."""
    body = {"type": type, "title": title, "description": description, "severity": severity, "orderId": order_id}
    event = await ctx.erp.post(f"/api/clients/{enc(client_id)}/events", without_none(body))
    return compact_event(event)


# ── Suppliers ──

SUPPLIER_TYPES = (
    "quality_issue, delivery_issue, shortage, return, credit_note, fight, price_change, price_negotiation, invoice_issue, "
    "payment, contract, certification, contact_change, compliment, call, visit, onboarding, note"
)
SupplierEventType = Literal[
    "quality_issue", "delivery_issue", "shortage", "return", "dispute", "price_change", "invoice_issue", "call", "note"
]


@tool
async def get_supplier_history(
    ctx: ToolContext,
    supplier_id: str = Field(description="ex. sup_0003"),
    types: list[str] | None = Field(None, description=f"Optional: Filter by type ({SUPPLIER_TYPES})"),
    limit: float | None = LIMIT,
) -> list[dict]:
    """
    History of the relationship with a supplier: quality problems, delays, breaks, price increases, disputes, contracts...
    Problems opened first, then from the latest to the oldest. Supplier relationship history, open issues first.
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
    title: str = Field(description="Short line in English, e.g. \"Product delivered not compliant\""),
    description: str | None = None,
    severity: Severity | None = None,
    purchase_order_id: str | None = Field(None, description="Optional: relevant supplier order (po_...)"),
) -> dict:
    """
    Record an event in a supplier's history, e.g., poor quality batch, incomplete delivery, failure.
    The problems are created "open". Record a beg event (quality issue, shortage, price change...).
    """
    body = {"type": type, "title": title, "description": description, "severity": severity, "purchaseOrderId": purchase_order_id}
    event = await ctx.erp.post(f"/api/suppliers/{enc(supplier_id)}/events", without_none(body))
    return compact_event(event)


def without_none(d: dict) -> dict:
    """Leave out the optional arguments the model did not give."""
    return {k: v for k, v in d.items() if v is not None}
