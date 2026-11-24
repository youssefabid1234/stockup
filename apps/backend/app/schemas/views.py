"""Response shapes of the HTTP API (summaries, details, computed views).

All routes are JSON under /api. Errors: {"error": {"code": str, "message": str}} with 4xx/5xx.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from app.schemas.base import Schema
from app.schemas.domain import (
    Client,
    ClientEvent,
    ClientStatus,
    ContextEntry,
    ContextEntityType,
    Id,
    Invoice,
    InvoiceLine,
    IsoDate,
    OrderBase,
    OrderLine,
    Payment,
    PaymentAllocation,
    PriceRule,
    Product,
    ProductCategory,
    PurchaseOrderBase,
    PurchaseOrderLine,
    Lot,
    Route,
    RouteRunBase,
    RouteStop,
    StockLevel,
    StockMovement,
    Supplier,
    SupplierEvent,
    SupplierPrice,
    TagDef,
    Unit,
)


class ApiErrorBody(Schema):
    code: str
    message: str


class ApiError(Schema):
    error: ApiErrorBody


class Ok(Schema):
    ok: Literal[True]


class Health(Schema):
    ok: Literal[True]
    today: IsoDate


WarningCode = Literal[
    "credit_limit", "client_blocked", "insufficient_stock", "expiring_soon", "no_route", "price_below_cost",
    # purchase orders
    "below_min_order", "price_above_usual", "not_in_supplier_catalog",
]  # fmt: skip


class Warning(Schema):
    """Non-blocking business warning returned by confirm/create endpoints."""

    code: WarningCode
    message: str  # French, human readable
    product_id: Id | None = None


# ───────── Dashboard & search ─────────


class LowStockItem(Schema):
    product_id: Id
    name: str
    available: float
    unit: str


class ExpiringLot(Schema):
    lot_id: Id
    product_id: Id
    name: str
    qty_remaining: float
    expires_at: IsoDate


class RevenueDay(Schema):
    date: IsoDate
    revenue: float


class TopClient(Schema):
    client_id: Id
    name: str
    revenue: float


class Dashboard(Schema):
    today: IsoDate
    revenue_today: float
    revenue_month: float
    orders_today: int
    draft_orders: int
    to_deliver_today: int
    overdue_invoices_amount: float
    overdue_invoices_count: int
    low_stock: list[LowStockItem]
    expiring_soon: list[ExpiringLot]
    revenue_by_day: list[RevenueDay]  # last 30 days
    top_clients: list[TopClient]  # last 30 days


class SearchResult(Schema):
    type: Literal["client", "product", "supplier", "order", "context"]
    id: Id
    label: str
    sublabel: str | None = None
    score: float


# ───────── Clients ─────────


class ClientSummary(Client):
    open_issues: int  # client events with status open
    outstanding: float  # € TTC unpaid
    overdue: float
    last_order_at: IsoDate | None = None
    revenue_30d: float


class UsualBasketLine(Schema):
    product_id: Id
    product_name: str
    unit: str
    avg_qty: float
    frequency: float  # share of orders containing it, 0..1
    last_qty: float
    last_ordered_at: IsoDate


class ClientPriceView(Schema):
    product_id: Id
    product_name: str
    price: float
    list_price: float


class ClientEventStats(Schema):
    total: int
    open: int
    complaints_12m: int
    returns_12m: int
    since: IsoDate | None = None


class OrderSummary(OrderBase):
    client_name: str
    line_count: int


class InvoiceSummary(Invoice):
    """List row: an invoice without its `lines` (lineCount instead); the detail has the lines."""

    lines: list[InvoiceLine] | None = None  # only on InvoiceDetail
    line_count: int
    client_name: str
    balance: float  # totalTtc - amountPaid
    days_overdue: int  # 0 if not overdue


class PaymentAllocationView(PaymentAllocation):
    invoice_number: str | None = None


class PaymentSummary(Payment):
    client_name: str
    allocations: list[PaymentAllocationView]  # with the invoice number


class ClientEventSummary(ClientEvent):
    client_name: str
    order_number: str | None = None  # CMD-… of the linked order
    invoice_number: str | None = None  # FAC-… of the linked invoice


class ClientDetail(ClientSummary):
    prices: list[ClientPriceView]
    recent_orders: list[OrderSummary]  # latest 20 (all: GET /api/orders?clientId=)
    open_invoices: list[InvoiceSummary]  # oldest due first, at most 100 (all: GET /api/invoices?clientId=&status=open)
    open_invoice_count: int
    payments: list[PaymentSummary]
    usual: list[UsualBasketLine]
    recent_events: list[ClientEventSummary]  # latest 10
    event_stats: ClientEventStats


# ───────── Suppliers & products ─────────


class SupplierEventSummary(SupplierEvent):
    supplier_name: str
    po_number: str | None = None  # ACH-… of the linked purchase order


class SupplierEventStats(Schema):
    total: int
    open: int
    issues_12m: int
    since: IsoDate | None = None


class SupplierPriceView(SupplierPrice):
    product_name: str
    unit: str


class PurchaseOrderSummary(PurchaseOrderBase):
    supplier_name: str
    line_count: int


class SupplierDetail(Supplier):
    open_issues: int
    recent_events: list[SupplierEventSummary]  # latest 10
    event_stats: SupplierEventStats
    prices: list[SupplierPriceView]
    purchase_orders: list[PurchaseOrderSummary]  # latest 60 (the full list: GET /api/purchase-orders?supplierId=)
    purchase_stats: PurchaseStats


class PurchaseStats(Schema):
    """Over ALL purchase orders of the supplier."""

    count: int
    open_count: int  # sent | partially_received
    open_total: float
    draft_count: int
    done_count: int  # neither draft nor cancelled
    done_total: float


class ProductSummary(Product):
    available: float
    on_hand: float
    next_expiry: IsoDate | None = None


class ProductSupplierPrice(SupplierPrice):
    supplier_name: str


class SalesStats(Schema):
    qty: float
    revenue: float


class ProductDetail(ProductSummary):
    stock: StockLevel
    supplier_prices: list[ProductSupplierPrice]
    movements: list[StockMovement]
    sales_30d: SalesStats


class StockItem(StockLevel):
    """A stock level with its product embedded (GET /api/stock)."""

    product: Product


# ───────── Orders, purchasing, billing ─────────


class OrderLineView(OrderLine):
    product_name: str
    unit: str
    available: float


class OrderDetail(OrderBase):
    client: Client
    lines: list[OrderLineView]
    warnings: list[Warning]
    invoice: InvoiceSummary | None = None


class PurchaseOrderLineView(PurchaseOrderLine):
    product_name: str
    unit: str


class PurchaseOrderDetail(PurchaseOrderBase):
    supplier: Supplier
    lines: list[PurchaseOrderLineView]
    lots: list[Lot]
    # Draft/sent only: below supplier minimum, price > usual supplier price +10 %, not in supplier catalogue.
    warnings: list[Warning] | None = None


class InvoiceDetail(InvoiceSummary):
    lines: list[InvoiceLine]
    client: Client
    payments: list[PaymentSummary]


class RouteStopView(RouteStop):
    client_name: str
    address: str
    city: str
    order_number: str
    weight_kg: float


class RouteRunDetail(RouteRunBase):
    route: Route
    stops: list[RouteStopView]
    total_weight_kg: float


# ───────── Pricing ─────────


class TagWithCount(TagDef):
    count: int


class PriceRuleSummary(PriceRule):
    client_scope_label: str  # "Tous les clients", "Groupe : Gastro", "Le Bistrot du Port"
    product_scope_label: str
    method_label: str  # "-8 % sur prix catalogue", "Prix fixe 24,50 €", "Coût +22 %"
    affected_products: int
    affected_clients: int


PriceSource = Literal["client_price", "rule", "list"]


class PriceCandidate(Schema):
    source: PriceSource
    rule_id: Id | None = None
    label: str
    price: float
    applied: bool
    reason: str | None = None


class ResolvedPrice(Schema):
    """The price an order line would get, and why."""

    client_id: Id
    product_id: Id
    qty: float
    price: float  # € HT / unit
    list_price: float
    cost: float
    margin_pct: float  # (price - cost) / price
    source: PriceSource
    rule_id: Id | None = None
    explanation: str  # "Règle « Gastro -8 % crustacés » (groupe Gastro × catégorie Crustacés)…"
    candidates: list[PriceCandidate]


class PriceGridRow(Schema):
    product_id: Id
    product_name: str
    sku: str
    unit: Unit
    category: ProductCategory
    tags: list[str]
    cost: float
    list_price: float
    price: float
    source: PriceSource
    rule_id: Id | None = None
    margin_pct: float


# ───────── Receivables ─────────


class AgingBuckets(Schema):
    """Aged balance buckets, by days past due date (TTC). "current" = not yet due."""

    current: float
    d1_30: float = Field(alias="d1_30")
    d31_60: float = Field(alias="d31_60")
    d61_90: float = Field(alias="d61_90")
    d90plus: float = Field(alias="d90plus")


class ReceivableRow(Schema):
    client_id: Id
    client_name: str
    client_code: str
    status: ClientStatus
    sales_rep: str
    zone: str
    tags: list[str]
    payment_terms_days: int
    credit_limit: float
    outstanding: float  # total unpaid TTC
    overdue: float  # unpaid TTC past due
    credit_used_pct: float  # outstanding / creditLimit (0 when no limit)
    buckets: AgingBuckets
    open_invoices: int
    oldest_due_date: IsoDate | None = None
    max_days_overdue: int
    last_payment_at: IsoDate | None = None
    last_payment_amount: float | None = None
    avg_days_to_pay: int | None = None  # over the last 90 days of paid invoices
    open_disputes: int  # open client events of type dispute
    last_reminder_at: IsoDate | None = None  # last late_payment client event
    # high if > limit, > 60 days overdue, blocked, or (avgDaysToPay > 60 and overdue > 0);
    # watch if > 80 % of limit, > 30 days overdue, an OPEN late_payment event, or avgDaysToPay > 45.
    risk: Literal["ok", "watch", "high"]


class ReceivablesTotals(AgingBuckets):
    outstanding: float
    overdue: float
    clients: int
    clients_overdue: int
    dso: int


class Receivables(Schema):
    as_of: IsoDate
    totals: ReceivablesTotals
    rows: list[ReceivableRow]  # sorted by overdue desc


# ───────── Context ─────────


class ContextEntrySummary(ContextEntry):
    entity_label: str  # "La Table d'Aurélien", "Crustacés"; "Entreprise" for entityType company
    score: float | None = None  # relevance (only with q)


class ContextForEntity(Schema):
    entity_type: ContextEntityType
    id: Id
    label: str
    entries: list[ContextEntrySummary]  # entries about this entity
    # Related: product → its category; supplier → the categories it sells; any → company/category entries citing its id.
    related: list[ContextEntrySummary]

