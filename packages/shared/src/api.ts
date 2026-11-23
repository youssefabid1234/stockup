/**
 * HTTP contract of the ERP API (apps/api, default http://localhost:4000).
 * All routes are JSON under /api. Errors: { error: { code: string, message: string } } with 4xx/5xx.
 * Every write accepts an optional header `x-actor: user|ai_chat|voice_agent` (+ `x-actor-name`)
 * which is recorded on the ActivityEvent.
 *
 * LISTS (every GET that returns a list): server-side pagination, filtering and sorting.
 *   ?limit= (default 100, max 500)  ?offset= (default 0)  ?sort=<field> ?order=asc|desc (fields listed per route)
 *   Response: a plain JSON array (the requested page) — or, with ?envelope=1, a Page<T>:
 *   { items, total, limit, offset, counts?, sums?, sumsByStatus?, countsByType?, countsBySource?, facets? }
 *   where the extras are computed over the WHOLE filtered set (tab counts ignore the tab/status filter).
 *
 * READ
 *  GET  /api/health
 *  GET  /api/meta                                  → DataPack["meta"]
 *  GET  /api/dashboard                             → Dashboard
 *  GET  /api/search?q=&types=client,product,supplier,order&limit=  → SearchResult[] (fuzzy, accents-insensitive, uses product aliases;
 *        add types=context to also match context entries — never included by default; limit default 20)
 *  GET  /api/clients?q=&type=&zone=&status=&tag=   → ClientSummary[]  sort: name|code|type|tags|zone|rep|city|outstanding|overdue|last|revenue30d|status
 *        (envelope: counts per status, facets.zone, facets.salesRep)
 *  GET  /api/clients/:id                           → ClientDetail (recentOrders: latest 20, openInvoices: at most 100 + openInvoiceCount)
 *  GET  /api/clients/:id/usual                     → UsualBasketLine[]  ("the usual": what this client typically orders)
 *  GET  /api/clients/:id/events?type=&status=&q=   → ClientEventSummary[] (newest first; sort=open → open issues first)
 *  GET  /api/client-events?type=&status=&clientId=&q=&from=&to=  → ClientEventSummary[] (newest first, all clients;
 *        envelope: counts per status, countsByType, sums.amount)
 *  GET  /api/categories                           → Category[] ({id, label}; per company, from seed/categories.json)
 *  GET  /api/suppliers?q=&category=&tag=           → Supplier[]  sort: name|city|tags|lead|terms|min
 *  GET  /api/suppliers/:id                         → SupplierDetail (purchaseOrders: latest 60 + purchaseStats over all)
 *  GET  /api/suppliers/:id/events?type=&status=&q= → SupplierEventSummary[] (newest first; sort=open → open issues first)
 *  GET  /api/supplier-events?type=&status=&supplierId=&q=&from=&to=  → SupplierEventSummary[]
 *  GET  /api/products?q=&category=&tag=&active=    → ProductSummary[]  sort: name|sku|category|tags|price|cost|margin|available|expiry
 *        (envelope: counts per category)
 *  GET  /api/products/:id                          → ProductDetail
 *  GET  /api/products/:id/alternatives             → ProductSummary[] (same category, available stock, close price)
 *  GET  /api/stock?q=&tab=out|low|expiring         → (StockLevel & { product })[]  sort: product|sku|category|onHand|reserved|available|incoming|expiry|state
 *        (envelope: counts per tab)
 *  GET  /api/stock/movements?productId=            → StockMovement[] (newest first; order=asc → oldest first)
 *  GET  /api/orders?status=&clientId=&date=&q=&source=  → OrderSummary[]  sort: number|client|date|createdAt|lines|total|status
 *        (envelope: counts per status, sums.totalHt)
 *  GET  /api/orders/:id                            → OrderDetail
 *  GET  /api/purchase-orders?status=&supplierId=&date=&q=  → PurchaseOrderSummary[]  sort: number|supplier|date|createdAt|lines|total|status
 *        (envelope: counts per status, sums.totalHt)
 *  GET  /api/purchase-orders/:id                   → PurchaseOrderDetail
 *  GET  /api/invoices?status=&clientId=&q=         → InvoiceSummary[] (no lines; status accepts overdue and the pseudo-status open)
 *        sort: number|client|issued|due|ttc|paid|balance|status (envelope: counts per status, sums, sumsByStatus)
 *  GET  /api/invoices/:id                          → InvoiceDetail
 *  GET  /api/payments?clientId=&method=&q=         → PaymentSummary[]  sort: date|client|method|ref|amount (envelope: sums.amount)
 *  GET  /api/receivables?q=&tag=&rep=&zone=&onlyOverdue=  → Receivables (aged balance per client, as of business today; one row per client, not paginated)
 *  GET  /api/routes                                → Route[]
 *  GET  /api/route-runs?date=&routeId=             → RouteRunDetail[] (newest date first)
 *  GET  /api/events?actor=user|ai&entity=          → ActivityEvent[] (newest first; default limit 50)
 *  GET  /api/events/stream                         → SSE, one `event: activity` per ActivityEvent
 *
 *  GET  /api/tags?scope=                           → (TagDef & { count: number })[]
 *  GET  /api/price-rules?active=&clientId=&productId=  → PriceRuleSummary[]
 *  GET  /api/prices/resolve?clientId=&productId=&qty=&date=  → ResolvedPrice (the price an order line would get, and why)
 *  GET  /api/prices/grid?clientId=|clientTag=&productTag=&category=&q=  → PriceGridRow[] (resolved price per product for one client or client group)
 *
 *  GET  /api/context?entityType=&entityId=&kind=&source=&tag=&q=  → ContextEntrySummary[] (context facts for the agents;
 *        entityType/kind/source comma-separated; q = accent-insensitive full text, results ranked by relevance when set)
 *        sort: title|entity|kind|tags|source|updated (envelope: counts per entityType, countsBySource)
 *  GET  /api/context/for?entityType=client|supplier|product|category&id=  → ContextForEntity (its own entries + related ones)
 *  GET  /api/context/:id                                  → ContextEntrySummary
 *
 * WRITE (business logic lives in the API, never in the UI)
 *  POST  /api/clients                     body ClientInput → Client
 *  PATCH /api/clients/:id                 body Partial<ClientInput> → Client
 *  POST  /api/clients/:id/notes           body { text, author } → Client
 *  POST  /api/clients/:id/events          body ClientEventInput → ClientEvent
 *  PATCH /api/client-events/:id           body Partial<ClientEventInput> & { status?, resolution? } → ClientEvent (resolving sets resolvedAt)
 *  POST  /api/tags                        body TagDef → TagDef ; PATCH /api/tags/:scope/:id ; DELETE /api/tags/:scope/:id (removes it from entities)
 *  PATCH /api/products/:id                body Partial<Pick<Product,"price"|"cost"|"tags"|"active"|"aliases">> → Product
 *  PATCH /api/suppliers/:id               body Partial<Pick<Supplier,"tags"|"notes"|"leadTimeDays"|"paymentTermsDays"|"minOrderAmount">> → Supplier
 *  (clients: PATCH /api/clients/:id accepts `tags`)
 *  PUT   /api/clients/:id/prices/:productId  body { price } → ClientPrice (negotiated price; upsert)
 *  DELETE /api/clients/:id/prices/:productId → { ok }
 *  POST  /api/price-rules                 body PriceRuleInput → PriceRule ; PATCH /api/price-rules/:id ; DELETE /api/price-rules/:id
 *  POST  /api/orders                      body OrderInput → OrderDetail  (status draft; prices resolved client price > list price)
 *  PATCH /api/orders/:id                  body { deliveryDate?, note? } → OrderDetail (draft/confirmed only)
 *  POST  /api/orders/:id/lines            body OrderLineInput → OrderDetail
 *  PATCH /api/orders/:id/lines/:lineId    body Partial<OrderLineInput> & { preparedQty? } → OrderDetail
 *  DELETE /api/orders/:id/lines/:lineId   → OrderDetail
 *  POST  /api/orders/:id/confirm          → OrderDetail  (checks client not blocked, credit limit, stock availability → warnings; reserves stock; assigns route run)
 *  POST  /api/orders/:id/prepare          body { lines?: {lineId, preparedQty}[] } → OrderDetail
 *  POST  /api/orders/:id/deliver          → OrderDetail  (consumes lots FEFO, stock movements, stop delivered)
 *  POST  /api/orders/:id/invoice          → InvoiceDetail
 *  POST  /api/orders/:id/cancel           → OrderDetail  (releases reservation)
 *  POST  /api/suppliers/:id/events        body SupplierEventInput → SupplierEvent
 *  PATCH /api/supplier-events/:id         body Partial<SupplierEventInput> & { status?, resolution? } → SupplierEvent
 *  POST  /api/purchase-orders             body PurchaseOrderInput → PurchaseOrderDetail (draft; prices from SupplierPrice; lines may be empty)
 *  PATCH /api/purchase-orders/:id          body { expectedDate?, note? } → PurchaseOrderDetail (draft/sent only)
 *  POST  /api/purchase-orders/:id/lines    body { productId, qty, unitPrice? } → PurchaseOrderDetail (draft only; price defaults to SupplierPrice, then product cost)
 *  PATCH /api/purchase-orders/:id/lines/:lineId  body { qty?, unitPrice?, productId? } → PurchaseOrderDetail (draft only)
 *  DELETE /api/purchase-orders/:id/lines/:lineId → PurchaseOrderDetail (draft only)
 *  GET   /api/suppliers/:id/usual          → UsualBasketLine[] (what we usually buy from this supplier, last 60 days)
 *  POST  /api/purchase-orders/:id/send    → PurchaseOrderDetail
 *  POST  /api/purchase-orders/:id/receive body { lines?: {lineId, receivedQty}[] } → PurchaseOrderDetail (creates lots, expiry = date + shelfLife)
 *  POST  /api/purchase-orders/:id/cancel  → PurchaseOrderDetail
 *  POST  /api/stock/adjust                body { productId, qty, reason: "adjustment"|"waste", note? } → StockLevel
 *  POST  /api/payments                    body PaymentInput → PaymentSummary (auto-allocates oldest open invoices if allocations omitted)
 *  POST  /api/route-runs/plan             body { date } → RouteRunDetail[] (groups confirmed/prepared orders of that date by client zone)
 *  PATCH /api/route-runs/:id/stops        body { orderIds: Id[] } → RouteRunDetail (reorder)
 *  POST  /api/context                    body ContextEntryInput → ContextEntry (source = the x-actor)
 *  PATCH /api/context/:id                body Partial<ContextEntryInput> → ContextEntry
 *  DELETE /api/context/:id               → { ok }
 *  POST  /api/admin/reset                 → { ok: true } (reload the data pack from DATA_DIR)
 */

import type {
  ActivityEvent,
  Client,
  ClientEvent,
  ContextEntry,
  ContextScope,
  SupplierEvent,
  PriceRule,
  ProductCategory,
  ClientType,
  Id,
  Invoice,
  IsoDate,
  Lot,
  Order,
  OrderLine,
  OrderSource,
  Payment,
  PaymentMethod,
  Product,
  PurchaseOrder,
  Route,
  RouteRun,
  StockLevel,
  StockMovement,
  Supplier,
  SupplierPrice,
} from "./domain";

// ── Lists ──
/** List params shared by every list route (server-side pagination + sort). */
export interface ListParams {
  /** Rows per page (default 100, max 500). */
  limit?: number;
  offset?: number;
  /** A sortable field of the route (see the route list above). */
  sort?: string;
  order?: "asc" | "desc";
}

/**
 * `?envelope=1` response of a list route. `total` = rows matching the filters. Extras are computed over the whole
 * filtered set: `counts` = rows per status / tab / category IGNORING that filter (tab badges); `sums` = footer totals
 * of the filtered rows; `sumsByStatus` = the same per status; `countsByType` (history) and `countsBySource` (context)
 * over the filtered rows; `facets` = every value of a filter field (filter menus).
 */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
  counts?: Record<string, number>;
  sums?: Record<string, number>;
  sumsByStatus?: Record<string, Record<string, number>>;
  countsByType?: Record<string, number>;
  countsBySource?: Record<string, number>;
  facets?: Record<string, string[]>;
}

export interface ApiError {
  error: { code: string; message: string };
}

/** Non-blocking business warnings returned by confirm/create endpoints. */
export interface Warning {
  code:
    | "credit_limit"
    | "client_blocked"
    | "insufficient_stock"
    | "expiring_soon"
    | "no_route"
    | "price_below_cost"
    // purchase orders
    | "below_min_order"
    | "price_above_usual"
    | "not_in_supplier_catalog";
  message: string; // French, human readable
  productId?: Id;
}

export interface Dashboard {
  today: IsoDate;
  revenueToday: number;
  revenueMonth: number;
  ordersToday: number;
  draftOrders: number;
  toDeliverToday: number;
  overdueInvoicesAmount: number;
  overdueInvoicesCount: number;
  lowStock: { productId: Id; name: string; available: number; unit: string }[];
  expiringSoon: { lotId: Id; productId: Id; name: string; qtyRemaining: number; expiresAt: IsoDate }[];
  revenueByDay: { date: IsoDate; revenue: number }[]; // last 30 days
  topClients: { clientId: Id; name: string; revenue: number }[]; // last 30 days
}

export interface SearchResult {
  type: "client" | "product" | "supplier" | "order" | "context";
  id: Id;
  label: string;
  sublabel?: string;
  score: number;
}

export interface ClientSummary extends Client {
  openIssues: number; // client events with status open
  outstanding: number; // € TTC unpaid
  overdue: number;
  lastOrderAt?: IsoDate;
  revenue30d: number;
}

export interface UsualBasketLine {
  productId: Id;
  productName: string;
  unit: string;
  avgQty: number;
  frequency: number; // share of orders containing it, 0..1
  lastQty: number;
  lastOrderedAt: IsoDate;
}

export interface ClientDetail extends ClientSummary {
  prices: { productId: Id; productName: string; price: number; listPrice: number }[];
  /** Latest 20 (all of them: GET /api/orders?clientId=). */
  recentOrders: OrderSummary[];
  /** Oldest due first, at most 100 (all of them: GET /api/invoices?clientId=&status=open). */
  openInvoices: InvoiceSummary[];
  openInvoiceCount: number;
  payments: PaymentSummary[];
  usual: UsualBasketLine[];
  recentEvents: ClientEvent[]; // latest 10
  eventStats: { total: number; open: number; complaints12m: number; returns12m: number; since?: IsoDate };
}

export interface SupplierDetail extends Supplier {
  openIssues: number;
  recentEvents: SupplierEvent[]; // latest 10
  eventStats: { total: number; open: number; issues12m: number; since?: IsoDate };
  prices: (SupplierPrice & { productName: string; unit: string })[];
  /** Latest 60 (all of them: GET /api/purchase-orders?supplierId=). */
  purchaseOrders: PurchaseOrderSummary[];
  /** Over ALL purchase orders of the supplier. */
  purchaseStats: {
    count: number;
    openCount: number; // sent | partially_received
    openTotal: number;
    draftCount: number;
    doneCount: number; // neither draft nor cancelled
    doneTotal: number;
  };
}

export interface ProductSummary extends Product {
  available: number;
  onHand: number;
  nextExpiry?: IsoDate;
}

export interface ProductDetail extends ProductSummary {
  stock: StockLevel;
  supplierPrices: (SupplierPrice & { supplierName: string })[];
  movements: StockMovement[];
  sales30d: { qty: number; revenue: number };
}

export interface OrderSummary extends Omit<Order, "lines"> {
  clientName: string;
  lineCount: number;
}

export interface OrderDetail extends Order {
  client: Client;
  lines: (OrderLine & { productName: string; unit: string; available: number })[];
  warnings: Warning[];
  invoice?: InvoiceSummary;
}

export interface PurchaseOrderSummary extends Omit<PurchaseOrder, "lines"> {
  supplierName: string;
  lineCount: number;
}

export interface PurchaseOrderDetail extends PurchaseOrder {
  supplier: Supplier;
  lines: (PurchaseOrder["lines"][number] & { productName: string; unit: string })[];
  lots: Lot[];
  /** Draft/sent only: below supplier minimum, price > usual supplier price +10 %, product not in supplier catalogue. */
  warnings?: Warning[];
}

/** List row: an invoice without its lines (the detail has them). */
export interface InvoiceSummary extends Omit<Invoice, "lines"> {
  lineCount: number;
  clientName: string;
  balance: number; // totalTtc - amountPaid
  daysOverdue: number; // 0 if not overdue
}

export interface InvoiceDetail extends InvoiceSummary {
  lines: Invoice["lines"];
  client: Client;
  payments: PaymentSummary[];
}

export interface PaymentSummary extends Omit<Payment, "allocations"> {
  clientName: string;
  allocations: (Payment["allocations"][number] & { invoiceNumber?: string })[];
}

export interface RouteRunDetail extends RouteRun {
  route: Route;
  stops: (RouteRun["stops"][number] & { clientName: string; address: string; city: string; orderNumber: string; weightKg: number })[];
  totalWeightKg: number;
}

// ── Inputs ──

export interface ClientEventSummary extends ClientEvent {
  clientName: string;
  /** Document numbers of the linked order / invoice (CMD-…, FAC-…), when linked. */
  orderNumber?: string;
  invoiceNumber?: string;
}

export interface ClientEventInput {
  type: ClientEvent["type"];
  title: string;
  description?: string;
  at?: string; // defaults to now (business clock)
  channel?: ClientEvent["channel"];
  author?: string;
  severity?: ClientEvent["severity"];
  status?: ClientEvent["status"];
  orderId?: Id;
  invoiceId?: Id;
  productIds?: Id[];
  amount?: number;
  tags?: string[];
}

export interface SupplierEventSummary extends SupplierEvent {
  supplierName: string;
  /** Document number of the linked purchase order (ACH-…), when linked. */
  poNumber?: string;
}

export interface SupplierEventInput {
  type: SupplierEvent["type"];
  title: string;
  description?: string;
  at?: string;
  channel?: SupplierEvent["channel"];
  author?: string;
  severity?: SupplierEvent["severity"];
  status?: SupplierEvent["status"];
  purchaseOrderId?: Id;
  productIds?: Id[];
  amount?: number;
  tags?: string[];
}

export interface PriceRuleSummary extends PriceRule {
  clientScopeLabel: string; // "Tous les clients", "Groupe : Gastro", "Le Bistrot du Port"
  productScopeLabel: string;
  methodLabel: string; // "-8 % sur prix catalogue", "Prix fixe 24,50 €", "Coût +22 %"
  affectedProducts: number;
  affectedClients: number;
}

export type PriceSource = "client_price" | "rule" | "list";

export interface ResolvedPrice {
  clientId: Id;
  productId: Id;
  qty: number;
  price: number; // € HT / unit
  listPrice: number;
  cost: number;
  marginPct: number; // (price - cost) / price
  source: PriceSource;
  ruleId?: Id;
  explanation: string; // French: "Règle « Gastro -8 % crustacés » (groupe Gastro × catégorie Crustacés)"
  candidates: { source: PriceSource; ruleId?: Id; label: string; price: number; applied: boolean; reason?: string }[];
}

export interface PriceGridRow {
  productId: Id;
  productName: string;
  sku: string;
  unit: string;
  category: ProductCategory;
  tags: string[];
  cost: number;
  listPrice: number;
  price: number;
  source: PriceSource;
  ruleId?: Id;
  marginPct: number;
}

export type PriceRuleInput = Omit<PriceRule, "id" | "createdAt" | "active" | "priority"> & { active?: boolean; priority?: number };

/** Aged balance buckets, by days past due date (TTC). "current" = not yet due. */
export interface AgingBuckets {
  current: number;
  d1_30: number;
  d31_60: number;
  d61_90: number;
  d90plus: number;
}

export interface ReceivableRow {
  clientId: Id;
  clientName: string;
  clientCode: string;
  status: Client["status"];
  salesRep: string;
  zone: string;
  tags: string[];
  paymentTermsDays: number;
  creditLimit: number;
  outstanding: number; // total unpaid TTC
  overdue: number; // unpaid TTC past due
  creditUsedPct: number; // outstanding / creditLimit (0 when no limit)
  buckets: AgingBuckets;
  openInvoices: number;
  oldestDueDate?: IsoDate;
  maxDaysOverdue: number;
  lastPaymentAt?: IsoDate;
  lastPaymentAmount?: number;
  avgDaysToPay?: number; // over the last 90 days of paid invoices
  openDisputes: number; // open client events of type dispute
  lastReminderAt?: IsoDate; // last late_payment client event
  /**
   * high if > limit, > 60 days overdue, blocked, or (avgDaysToPay > 60 and overdue > 0);
   * watch if > 80 % of limit, > 30 days overdue, an OPEN late_payment client event, or avgDaysToPay > 45.
   */
  risk: "ok" | "watch" | "high";
}

export interface Receivables {
  asOf: IsoDate;
  totals: AgingBuckets & { outstanding: number; overdue: number; clients: number; clientsOverdue: number; dso: number };
  rows: ReceivableRow[]; // sorted by overdue desc
}

export interface ClientInput {
  name: string;
  type: ClientType;
  contacts?: Client["contacts"];
  address?: string;
  city?: string;
  zone?: string;
  deliveryDays?: Client["deliveryDays"];
  paymentTermsDays?: number;
  creditLimit?: number;
  status?: Client["status"];
  salesRep?: string;
  preferences?: string;
  tags?: string[];
}

export interface OrderLineInput {
  productId: Id;
  qty: number;
  unitPrice?: number; // defaults to client price, then list price
  note?: string;
  substituteFor?: Id;
}

export interface OrderInput {
  clientId: Id;
  deliveryDate?: IsoDate; // defaults to next delivery day of the client
  source?: OrderSource;
  lines?: OrderLineInput[];
  note?: string;
}

export interface PurchaseOrderInput {
  supplierId: Id;
  expectedDate?: IsoDate;
  lines: { productId: Id; qty: number; unitPrice?: number }[]; // may be [] → empty draft
  note?: string;
}

export interface PaymentInput {
  clientId: Id;
  amount: number;
  method: PaymentMethod;
  receivedAt?: IsoDate;
  reference?: string;
  allocations?: { invoiceId: Id; amount: number }[];
}

// ── Context ──

export interface ContextEntrySummary extends ContextEntry {
  /** Name of the entity it is about ("La Table d'Aurélien", "Crustacés"); "Entreprise" for scope company. */
  entityLabel: string;
  /** Relevance (only with q). */
  score?: number;
}

export interface ContextEntryInput {
  entityType: ContextScope;
  entityId?: Id; // required unless scope = company
  kind: ContextEntry["kind"];
  title: string;
  body: string;
  tags?: string[];
}

export interface ContextForEntity {
  entityType: ContextScope;
  id: Id;
  label: string;
  /** Entries about this entity. */
  entries: ContextEntrySummary[];
  /** Related: product → its category; supplier → the categories it sells; any → company/category entries that cite its id. */
  related: ContextEntrySummary[];
}

export type { ActivityEvent, Client, Invoice, Order, Payment, Product, PurchaseOrder, Route, RouteRun, StockLevel, Supplier };
