"""Domain model of the Voice ERP kit — a food wholesaler (seafood + fresh produce).

THE contract shared by backend, ai, web and the data pack (the web app's TypeScript types are
generated from the OpenAPI schema built from these classes). Change it only additively.

Conventions
- ids: short prefixed strings ("cli_0012", "prd_0042", "ord_000123").
- money: euros as numbers with 2 decimals (HT = excl. VAT unless named *Ttc).
- quantities: numbers in the product's unit (kg may be decimal).
- dates: ISO strings. `date` fields are "YYYY-MM-DD", `at` fields are full ISO timestamps.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from app.schemas.base import Schema

Id = str
IsoDate = str  # YYYY-MM-DD
IsoDateTime = str  # full ISO

# ───────────────────────── Catalogue ─────────────────────────

Unit = Literal["kg", "piece", "box", "dozen", "liter"]
ProductCategory = str  # per-company slug ("boeuf", "vins-rouges"…); labels in seed/categories.json (GET /api/categories)


class Category(Schema):
    id: str
    label: str


class Product(Schema):
    id: Id
    sku: str  # "BAR-LIG-12"
    name: str  # "Bar de ligne 1-2 kg"
    aliases: list[str]  # what people actually say: ["loup", "bar", "seabass"]
    category: ProductCategory
    unit: Unit
    price: float  # list sell price €/unit HT
    cost: float  # reference purchase cost €/unit HT
    vat_rate: float  # 0.055 for food in France
    shelf_life_days: int
    origin: str | None = None  # "Bretagne", "Écosse"
    caliber: str | None = None  # "1-2 kg", "n°3"
    main_supplier_id: Id | None = None
    active: bool
    tags: list[str] | None = None  # product groups, e.g. ["premium", "fetes"] — see TagDef


# ───────────────────────── Partners ─────────────────────────

ClientType = Literal["restaurant", "brasserie", "fishmonger", "canteen", "supermarket", "caterer", "hotel"]
Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
ClientStatus = Literal["active", "blocked", "prospect"]


class Contact(Schema):
    name: str
    role: str | None = None  # "Chef", "Gérant", "Acheteur"
    phone: str | None = None
    email: str | None = None


class ClientNote(Schema):
    at: IsoDateTime
    author: str  # "Sophie (commerciale)"
    text: str  # "Ne veut jamais de substitution sur le bar"


class Client(Schema):
    id: Id
    code: str  # "C0012"
    name: str  # "Le Bistrot du Port"
    type: ClientType
    contacts: list[Contact]
    address: str
    city: str
    zone: str  # delivery zone, matches Route.zone
    delivery_days: list[Weekday]
    payment_terms_days: int  # 0 = cash on delivery
    credit_limit: float  # € TTC outstanding allowed
    status: ClientStatus
    sales_rep: str
    preferences: str  # short free text summary of habits
    notes: list[ClientNote]
    created_at: IsoDateTime
    tags: list[str] | None = None  # client groups, e.g. ["gastro", "grands-comptes"]


class ClientPrice(Schema):
    """Negotiated price for one client on one product (overrides Product.price)."""

    client_id: Id
    product_id: Id
    price: float


class Supplier(Schema):
    id: Id
    name: str
    contacts: list[Contact]
    city: str
    categories: list[ProductCategory]
    lead_time_days: int
    payment_terms_days: int
    min_order_amount: float
    notes: str
    tags: list[str] | None = None  # supplier groups, e.g. ["criee", "importateur", "bio"]


class SupplierPrice(Schema):
    """Current purchase price of a product at a supplier."""

    supplier_id: Id
    product_id: Id
    price: float
    updated_at: IsoDate


# ───────────────────────── Stock ─────────────────────────


class Lot(Schema):
    """A received batch of one product. Stock is FEFO (first expired, first out)."""

    id: Id
    product_id: Id
    supplier_id: Id | None = None
    purchase_order_id: Id | None = None
    qty_received: float
    qty_remaining: float
    received_at: IsoDate
    expires_at: IsoDate


StockMovementReason = Literal["receipt", "sale", "adjustment", "waste", "return"]


class StockMovement(Schema):
    id: Id
    at: IsoDateTime
    product_id: Id
    lot_id: Id | None = None
    qty: float  # + in, - out
    reason: StockMovementReason
    ref_type: Literal["order", "purchase_order", "manual"] | None = None
    ref_id: Id | None = None
    note: str | None = None


class StockLevel(Schema):
    """Computed view, not stored."""

    product_id: Id
    on_hand: float  # sum of lots remaining
    reserved: float  # confirmed/prepared orders not yet delivered
    available: float  # onHand - reserved
    incoming: float  # open purchase orders not yet received
    next_expiry: IsoDate | None = None
    lots: list[Lot]


# ───────────────────────── Sales ─────────────────────────

# draft = pré-commande (captured, not committed) · confirmed = stock reserved · prepared = picked & weighed
# delivered = left the warehouse, stock consumed (FEFO) · invoiced · cancelled
OrderStatus = Literal["draft", "confirmed", "prepared", "delivered", "invoiced", "cancelled"]
OrderSource = Literal["phone", "voice_agent", "email", "whatsapp", "manual", "web"]


class OrderLine(Schema):
    id: Id
    product_id: Id
    qty: float
    unit_price: float  # € HT, resolved from ClientPrice / rules / Product.price at creation
    prepared_qty: float | None = None  # actual weight/quantity picked
    note: str | None = None  # "bien frais", "sans tête"
    substitute_for: Id | None = None  # productId this line replaces


class OrderBase(Schema):
    """An order without its lines (what list views return)."""

    id: Id
    number: str  # "CMD-2026-000123"
    client_id: Id
    status: OrderStatus
    source: OrderSource
    delivery_date: IsoDate
    route_run_id: Id | None = None
    total_ht: float  # computed on write
    note: str | None = None
    created_at: IsoDateTime
    created_by: str  # "sophie" | "voice_agent" | ...
    confirmed_at: IsoDateTime | None = None
    delivered_at: IsoDateTime | None = None
    invoice_id: Id | None = None


class Order(OrderBase):
    lines: list[OrderLine]


# ───────────────────────── Purchasing ─────────────────────────

PurchaseOrderStatus = Literal["draft", "sent", "partially_received", "received", "cancelled"]


class PurchaseOrderLine(Schema):
    id: Id
    product_id: Id
    qty: float
    unit_price: float
    received_qty: float


class PurchaseOrderBase(Schema):
    id: Id
    number: str  # "ACH-2026-000045"
    supplier_id: Id
    status: PurchaseOrderStatus
    expected_date: IsoDate
    total_ht: float
    created_at: IsoDateTime
    note: str | None = None


class PurchaseOrder(PurchaseOrderBase):
    lines: list[PurchaseOrderLine]


# ───────────────────────── Billing ─────────────────────────

# issued → partially_paid → paid ; "overdue" is computed (issued/partially_paid past dueDate).
InvoiceStatus = Literal["draft", "issued", "partially_paid", "paid", "overdue", "cancelled"]


class InvoiceLine(Schema):
    product_id: Id
    label: str
    qty: float
    unit_price: float
    vat_rate: float
    total_ht: float


class Invoice(Schema):
    id: Id
    number: str  # "FAC-2026-000210"
    client_id: Id
    order_ids: list[Id]
    status: InvoiceStatus
    issued_at: IsoDate
    due_date: IsoDate
    lines: list[InvoiceLine]
    total_ht: float
    total_vat: float
    total_ttc: float
    amount_paid: float


PaymentMethod = Literal["transfer", "card", "cheque", "cash", "direct_debit"]


class PaymentAllocation(Schema):
    invoice_id: Id
    amount: float


class Payment(Schema):
    id: Id
    client_id: Id
    amount: float  # € TTC
    method: PaymentMethod
    received_at: IsoDate
    reference: str | None = None
    allocations: list[PaymentAllocation]


# ───────────────────────── Logistics ─────────────────────────


class Route(Schema):
    """A recurring delivery route (tournée)."""

    id: Id
    name: str  # "Tournée Paris Ouest"
    zone: str
    driver: str
    vehicle: str  # "Camion frigo 12 m³"
    capacity_kg: float
    days: list[Weekday]
    departure_time: str  # "05:30"


StopStatus = Literal["pending", "delivered", "failed"]


class RouteStop(Schema):
    order_id: Id
    client_id: Id
    seq: int
    eta: str | None = None  # "07:10"
    status: StopStatus
    note: str | None = None


class RouteRunBase(Schema):
    """One route on one date."""

    id: Id
    route_id: Id
    date: IsoDate
    status: Literal["planned", "in_progress", "done"]


class RouteRun(RouteRunBase):
    stops: list[RouteStop]


# ───────────────────────── Activity ─────────────────────────

Actor = Literal["user", "ai_chat", "voice_agent", "system"]
ActivityEntity = Literal[
    "client", "supplier", "product", "stock", "order", "purchase_order", "invoice", "payment", "route_run", "context"
]


class ActivityEvent(Schema):
    """Every write appends one. Streamed live to the UI (SSE /api/events/stream)."""

    id: Id
    at: IsoDateTime
    actor: Actor
    actor_name: str | None = None
    type: str  # "order.created", "order.confirmed", "payment.recorded", ...
    entity: ActivityEntity
    entity_id: Id
    summary: str  # French sentence: "Commande CMD-… confirmée pour Le Bistrot du Port"


# ───────────────────────── Client / supplier history ─────────────────────────

ClientEventType = Literal[
    "onboarding", "call", "visit", "complaint", "quality_issue", "delivery_issue", "return", "credit_note", "dispute",
    "late_payment", "payment_plan", "price_negotiation", "special_request", "menu_change", "contact_change",
    "compliment", "churn_risk", "won_back", "note",
]  # fmt: skip
EventChannel = Literal["phone", "email", "whatsapp", "visit", "voice_agent", "sms", "other"]
Severity = Literal["low", "medium", "high"]
IssueStatus = Literal["open", "resolved"]


class ClientEvent(Schema):
    """Long-term relationship history with a client: complaints, returns, disputes, calls, visits…"""

    id: Id  # "cev_000123"
    client_id: Id
    at: IsoDateTime
    type: ClientEventType
    title: str  # "Réclamation : langoustines arrivées mortes"
    description: str
    channel: EventChannel | None = None
    author: str  # "Sophie (commerciale)", "Agent vocal"
    severity: Severity | None = None
    status: IssueStatus | None = None  # for issues
    resolved_at: IsoDateTime | None = None
    resolution: str | None = None  # "Avoir de 84 € accordé, lot remplacé le lendemain"
    order_id: Id | None = None
    invoice_id: Id | None = None
    product_ids: list[Id] | None = None
    amount: float | None = None  # € involved
    tags: list[str] | None = None


SupplierEventType = Literal[
    "onboarding", "call", "visit", "quality_issue", "delivery_issue", "shortage", "return", "credit_note", "dispute",
    "price_change", "price_negotiation", "invoice_issue", "payment", "contract", "certification", "contact_change",
    "compliment", "note",
]  # fmt: skip


class SupplierEvent(Schema):
    """Same idea for suppliers: the long-term history of our relationship with them."""

    id: Id  # "sev_000123"
    supplier_id: Id
    at: IsoDateTime
    type: SupplierEventType
    title: str
    description: str
    channel: EventChannel | None = None
    author: str
    severity: Severity | None = None
    status: IssueStatus | None = None
    resolved_at: IsoDateTime | None = None
    resolution: str | None = None
    purchase_order_id: Id | None = None
    product_ids: list[Id] | None = None
    amount: float | None = None
    tags: list[str] | None = None


# ───────────────────────── Groups (tags) & pricing ─────────────────────────

TagScope = Literal["client", "supplier", "product"]
TagColor = Literal["green", "teal", "amber", "blue", "rose", "violet", "gray"]


class TagDef(Schema):
    """A group/tag definition. Entities carry tag ids in their `tags` array."""

    id: str  # slug, unique per scope: "gastro", "premium"
    scope: TagScope
    label: str  # "Restaurants gastronomiques"
    color: TagColor | None = None
    description: str | None = None


class AllClientsScope(Schema):
    kind: Literal["all"]


class OneClientScope(Schema):
    kind: Literal["client"]
    client_id: Id


class ClientTagScope(Schema):
    kind: Literal["tag"]
    tag: str  # client group


PriceRuleClientScope = Annotated[Union[AllClientsScope, OneClientScope, ClientTagScope], Field(discriminator="kind")]


class AllProductsScope(Schema):
    kind: Literal["all"]


class OneProductScope(Schema):
    kind: Literal["product"]
    product_id: Id


class ProductTagScope(Schema):
    kind: Literal["tag"]
    tag: str  # product group


class CategoryScope(Schema):
    kind: Literal["category"]
    category: ProductCategory


PriceRuleProductScope = Annotated[
    Union[AllProductsScope, OneProductScope, ProductTagScope, CategoryScope], Field(discriminator="kind")
]


class FixedPrice(Schema):
    kind: Literal["fixed"]
    price: float  # € HT per unit


class DiscountPct(Schema):
    kind: Literal["discount_pct"]
    pct: float  # % off the list price


class MarkupPct(Schema):
    kind: Literal["markup_pct"]
    pct: float  # % on top of the product cost


PriceRuleMethod = Annotated[Union[FixedPrice, DiscountPct, MarkupPct], Field(discriminator="kind")]


class PriceRule(Schema):
    """Pricing rule for a group of clients × a group of products.

    Resolution (most specific wins, then higher priority, then most recent):
      1. ClientPrice (explicit negotiated price client × product)
      2. PriceRule client+product > client+tag/category > clientTag+product > clientTag+productTag/category > all-clients
      3. Product.price (list price)
    Rules respect validity dates and minQty.
    """

    id: Id  # "prl_0001"
    name: str  # "Gastro : -8 % sur les crustacés"
    active: bool
    priority: int  # tie-breaker, higher wins
    client_scope: PriceRuleClientScope
    product_scope: PriceRuleProductScope
    method: PriceRuleMethod
    min_qty: float | None = None
    valid_from: IsoDate | None = None
    valid_to: IsoDate | None = None
    note: str | None = None
    created_at: IsoDateTime


# ───────────────────────── Context (what the agent should know) ─────────────────────────

# What a context entry is about. `category` entries use a ProductCategory as entityId.
ContextEntityType = Literal["company", "client", "supplier", "product", "category"]
# policy = a rule · procedure = how to do/say something · preference = what they like · fact = background
# relationship = people · pricing = agreements · logistics = delivery, storage · risk = irritants, credit, churn
ContextKind = Literal["policy", "procedure", "preference", "fact", "relationship", "pricing", "logistics", "risk"]
# Who wrote the entry: the data pack, a person in the UI, or an agent during a chat / call.
ContextSource = Literal["seed", "user", "ai_chat", "voice_agent"]


class ContextEntry(Schema):
    """One short, editable, queryable piece of business knowledge for the agents."""

    id: Id  # "ctx_0001"
    entity_type: ContextEntityType
    entity_id: Id | None = None  # cli_…, sup_…, prd_… or a ProductCategory; absent for scope "company"
    kind: ContextKind
    title: str  # "Comment leur parler"
    body: str  # short markdown
    tags: list[str] | None = None  # free keywords: ["substitution", "dossier-ouvert"]
    source: ContextSource | None = None
    created_at: IsoDateTime
    updated_at: IsoDateTime


# ───────────────────────── Data pack ─────────────────────────


class Meta(Schema):
    """meta.json of the data pack (GET /api/meta)."""

    company: str
    today: IsoDate
    currency: Literal["EUR"]
    generated_at: IsoDateTime
    trade: str | None = None  # "fruits et légumes", from DATA_DIR/stats.json when present
    region: str | None = None  # "Lyon et Rhône"
    categories: list[Category] | None = None  # product categories of the pack, with French labels
