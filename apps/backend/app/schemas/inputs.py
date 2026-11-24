"""Request bodies. Every write accepts an optional header `x-actor: user|ai_chat|voice_agent`
(+ `x-actor-name`), recorded on the ActivityEvent.

Field order matters a little: activity summaries list the changed fields in this order.
"""

from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, StringConstraints

from app.schemas.base import Input
from app.schemas.domain import (
    ClientEventType,
    ClientStatus,
    ClientType,
    ContextKind,
    ContextEntityType,
    EventChannel,
    Id,
    IssueStatus,
    OrderSource,
    PaymentMethod,
    PriceRuleClientScope,
    PriceRuleMethod,
    PriceRuleProductScope,
    Severity,
    SupplierEventType,
    TagColor,
    TagScope,
    Weekday,
)


def _pattern(regex: str, message: str):
    """A string that must match `regex`, with a French error message."""

    def check(v: str) -> str:
        if not re.match(regex, v):
            raise ValueError(message)
        return v

    return AfterValidator(check)


IsoDateStr = Annotated[str, _pattern(r"^\d{4}-\d{2}-\d{2}$", "format AAAA-MM-JJ attendu")]
IsoDateTimeStr = Annotated[str, _pattern(r"^\d{4}-\d{2}-\d{2}(T.*)?$", "date ISO attendue")]
Slug = Annotated[str, _pattern(r"^[a-z0-9][a-z0-9-_]*$", "slug attendu (a-z, 0-9, -)")]
NonEmpty = Annotated[str, Field(min_length=1)]
Positive = Annotated[float, Field(gt=0)]
NonNegative = Annotated[float, Field(ge=0)]
NonNegativeInt = Annotated[int, Field(ge=0)]

# ───────── Clients ─────────


class ContactInput(Input):
    name: NonEmpty
    role: str | None = None
    phone: str | None = None
    email: str | None = None


class ClientInput(Input):
    name: NonEmpty
    type: ClientType
    contacts: list[ContactInput] | None = None
    address: str | None = None
    city: str | None = None
    zone: str | None = None
    delivery_days: list[Weekday] | None = None
    payment_terms_days: NonNegativeInt | None = None
    credit_limit: NonNegative | None = None
    status: ClientStatus | None = None
    sales_rep: str | None = None
    preferences: str | None = None
    tags: list[NonEmpty] | None = None


class ClientPatch(Input):
    """PATCH /api/clients/:id — any ClientInput field (including `tags`)."""

    name: NonEmpty | None = None
    type: ClientType | None = None
    contacts: list[ContactInput] | None = None
    address: str | None = None
    city: str | None = None
    zone: str | None = None
    delivery_days: list[Weekday] | None = None
    payment_terms_days: NonNegativeInt | None = None
    credit_limit: NonNegative | None = None
    status: ClientStatus | None = None
    sales_rep: str | None = None
    preferences: str | None = None
    tags: list[NonEmpty] | None = None


class ClientNoteInput(Input):
    text: NonEmpty
    author: str = "Équipe"


class ClientPriceInput(Input):
    price: Positive


# ───────── Client / supplier history ─────────


class ClientEventInput(Input):
    title: NonEmpty
    description: str | None = None
    at: IsoDateTimeStr | None = None  # defaults to now (business clock); a bare date means 09:00
    channel: EventChannel | None = None
    author: NonEmpty | None = None
    severity: Severity | None = None
    status: IssueStatus | None = None
    product_ids: list[str] | None = None
    amount: float | None = None
    tags: list[str] | None = None
    type: ClientEventType
    order_id: str | None = None
    invoice_id: str | None = None


class ClientEventPatch(Input):
    """Resolving (status → resolved) sets resolvedAt."""

    title: NonEmpty | None = None
    description: str | None = None
    at: IsoDateTimeStr | None = None
    channel: EventChannel | None = None
    author: NonEmpty | None = None
    severity: Severity | None = None
    status: IssueStatus | None = None
    product_ids: list[str] | None = None
    amount: float | None = None
    tags: list[str] | None = None
    type: ClientEventType | None = None
    order_id: str | None = None
    invoice_id: str | None = None
    resolution: str | None = None


class SupplierEventInput(Input):
    title: NonEmpty
    description: str | None = None
    at: IsoDateTimeStr | None = None
    channel: EventChannel | None = None
    author: NonEmpty | None = None
    severity: Severity | None = None
    status: IssueStatus | None = None
    product_ids: list[str] | None = None
    amount: float | None = None
    tags: list[str] | None = None
    type: SupplierEventType
    purchase_order_id: str | None = None


class SupplierEventPatch(Input):
    title: NonEmpty | None = None
    description: str | None = None
    at: IsoDateTimeStr | None = None
    channel: EventChannel | None = None
    author: NonEmpty | None = None
    severity: Severity | None = None
    status: IssueStatus | None = None
    product_ids: list[str] | None = None
    amount: float | None = None
    tags: list[str] | None = None
    type: SupplierEventType | None = None
    purchase_order_id: str | None = None
    resolution: str | None = None


# ───────── Catalogue, groups & pricing ─────────


class ProductPatch(Input):
    price: Positive | None = None
    cost: NonNegative | None = None
    tags: list[NonEmpty] | None = None
    active: bool | None = None
    aliases: list[str] | None = None


class SupplierPatch(Input):
    tags: list[NonEmpty] | None = None
    notes: str | None = None
    lead_time_days: NonNegativeInt | None = None
    payment_terms_days: NonNegativeInt | None = None
    min_order_amount: NonNegative | None = None


class TagInput(Input):
    id: Slug
    scope: TagScope
    label: NonEmpty
    color: TagColor | None = None
    description: str | None = None


class TagPatch(Input):
    label: NonEmpty | None = None
    color: TagColor | None = None
    description: str | None = None


class PriceRuleInput(Input):
    name: NonEmpty
    active: bool | None = None  # default true
    priority: int | None = None  # default 0
    client_scope: PriceRuleClientScope
    product_scope: PriceRuleProductScope
    method: PriceRuleMethod
    min_qty: Positive | None = None
    valid_from: IsoDateStr | None = None
    valid_to: IsoDateStr | None = None
    note: str | None = None


class PriceRulePatch(Input):
    name: NonEmpty | None = None
    active: bool | None = None
    priority: int | None = None
    client_scope: PriceRuleClientScope | None = None
    product_scope: PriceRuleProductScope | None = None
    method: PriceRuleMethod | None = None
    min_qty: Positive | None = None
    valid_from: IsoDateStr | None = None
    valid_to: IsoDateStr | None = None
    note: str | None = None


# ───────── Stock ─────────


class StockAdjustInput(Input):
    product_id: str
    qty: float  # > 0 adds a lot, < 0 removes FEFO; "waste" always removes
    reason: Literal["adjustment", "waste"]
    note: str | None = None


# ───────── Orders ─────────


class OrderLineInput(Input):
    product_id: NonEmpty
    qty: Positive
    unit_price: NonNegative | None = None  # defaults to the resolved client price
    note: str | None = None
    substitute_for: Id | None = None


class OrderInput(Input):
    client_id: NonEmpty
    delivery_date: IsoDateStr | None = None  # defaults to the client's next delivery day
    source: OrderSource | None = None
    lines: list[OrderLineInput] | None = None
    note: str | None = None


class OrderPatch(Input):
    delivery_date: IsoDateStr | None = None
    note: str | None = None


class OrderLinePatch(Input):
    product_id: NonEmpty | None = None
    qty: Positive | None = None
    unit_price: NonNegative | None = None
    note: str | None = None
    substitute_for: Id | None = None
    prepared_qty: NonNegative | None = None


class PreparedLine(Input):
    line_id: str
    prepared_qty: NonNegative


class PrepareInput(Input):
    """Lines not listed are considered picked exactly as ordered."""

    lines: list[PreparedLine] | None = None


# ───────── Purchasing ─────────


class PurchaseOrderLineInput(Input):
    product_id: NonEmpty
    qty: Positive
    unit_price: NonNegative | None = None  # defaults to the supplier price, then the product cost


class PurchaseOrderInput(Input):
    supplier_id: NonEmpty
    expected_date: IsoDateStr | None = None
    lines: list[PurchaseOrderLineInput] = []  # may be [] → empty draft
    note: str | None = None


class PurchaseOrderPatch(Input):
    expected_date: IsoDateStr | None = None
    note: str | None = None


class PurchaseOrderLinePatch(Input):
    product_id: NonEmpty | None = None
    qty: Positive | None = None
    unit_price: NonNegative | None = None


class ReceivedLine(Input):
    line_id: str
    received_qty: NonNegative  # received NOW (added to what was already received)


class ReceiveInput(Input):
    """Without `lines`, everything still outstanding is received."""

    lines: list[ReceivedLine] | None = None


# ───────── Billing & logistics ─────────


class AllocationInput(Input):
    invoice_id: str
    amount: Positive


class PaymentInput(Input):
    client_id: NonEmpty
    amount: Positive
    method: PaymentMethod
    received_at: IsoDateStr | None = None
    reference: str | None = None
    allocations: list[AllocationInput] | None = None  # omitted → oldest open invoices first


class PlanInput(Input):
    date: IsoDateStr | None = None  # default today


class ReorderStopsInput(Input):
    order_ids: list[str]


# ───────── Context ─────────

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Body = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=8000)]


class ContextEntryInput(Input):
    entity_type: ContextEntityType
    entity_id: NonEmpty | None = None  # required unless entityType = company
    kind: ContextKind
    title: Title
    body: Body
    tags: list[str] | None = None


class ContextEntryPatch(Input):
    entity_type: ContextEntityType | None = None
    entity_id: NonEmpty | None = None
    kind: ContextKind | None = None
    title: Title | None = None
    body: Body | None = None
    tags: list[str] | None = None
