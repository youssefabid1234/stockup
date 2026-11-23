/**
 * Domain model of the Voice ERP kit — a food wholesaler (seafood + fresh produce).
 * THE contract shared by api, ai, web and the data pack. Change it only additively.
 *
 * Conventions
 * - ids: short prefixed strings ("cli_0012", "prd_0042", "ord_000123").
 * - money: euros as numbers with 2 decimals (HT = excl. VAT unless named *Ttc).
 * - quantities: numbers in the product's unit (kg may be decimal).
 * - dates: ISO strings. `date` fields are "YYYY-MM-DD", `at` fields are full ISO timestamps.
 */

export type Id = string;
export type IsoDate = string; // YYYY-MM-DD
export type IsoDateTime = string; // full ISO

// ───────────────────────── Catalogue ─────────────────────────

export type Unit = "kg" | "piece" | "box" | "dozen" | "liter";
/**
 * Product category id: a slug defined per company by the data pack ("boeuf", "vins-rouges", "legumes"…).
 * The list with French labels is in meta.json `categories` (GET /api/categories).
 */
export type ProductCategory = string;

/** One product category of the company: slug id + French label ("Vins rouges"). */
export interface Category {
  id: ProductCategory;
  label: string;
}

export interface Product {
  id: Id;
  sku: string; // "BAR-LIG-12"
  name: string; // "Bar de ligne 1-2 kg"
  aliases: string[]; // what people actually say: ["loup", "bar", "seabass"]
  category: ProductCategory;
  unit: Unit;
  price: number; // list sell price €/unit HT
  cost: number; // reference purchase cost €/unit HT
  vatRate: number; // 0.055 for food in France
  shelfLifeDays: number;
  origin?: string; // "Bretagne", "Écosse"
  caliber?: string; // "1-2 kg", "n°3"
  mainSupplierId?: Id;
  active: boolean;
  tags?: string[]; // product groups, e.g. ["premium", "fetes", "bretagne"] — see TagDef
}

// ───────────────────────── Partners ─────────────────────────

export type ClientType =
  | "restaurant"
  | "brasserie"
  | "fishmonger"
  | "canteen"
  | "supermarket"
  | "caterer"
  | "hotel";

export type Weekday = "mon" | "tue" | "wed" | "thu" | "fri" | "sat" | "sun";

export interface Contact {
  name: string;
  role?: string; // "Chef", "Gérant", "Acheteur"
  phone?: string;
  email?: string;
}

export interface ClientNote {
  at: IsoDateTime;
  author: string; // "Sophie (commerciale)"
  text: string; // free text, e.g. "Ne veut jamais de substitution sur le bar"
}

export interface Client {
  id: Id;
  code: string; // "C0012"
  name: string; // "Le Bistrot du Port"
  type: ClientType;
  contacts: Contact[];
  address: string;
  city: string;
  zone: string; // delivery zone, matches Route.zone
  deliveryDays: Weekday[];
  paymentTermsDays: number; // 0 = cash on delivery
  creditLimit: number; // € TTC outstanding allowed
  status: "active" | "blocked" | "prospect";
  salesRep: string;
  preferences: string; // short free text summary of habits
  notes: ClientNote[];
  createdAt: IsoDateTime;
  tags?: string[]; // client groups, e.g. ["gastro", "grands-comptes", "marche-public"]
}

/** Negotiated price for one client on one product (overrides Product.price). */
export interface ClientPrice {
  clientId: Id;
  productId: Id;
  price: number;
}

export interface Supplier {
  id: Id;
  name: string;
  contacts: Contact[];
  city: string;
  categories: ProductCategory[];
  leadTimeDays: number;
  paymentTermsDays: number;
  minOrderAmount: number;
  notes: string;
  tags?: string[]; // supplier groups, e.g. ["criee", "importateur", "bio"]
}

/** Current purchase price of a product at a supplier. */
export interface SupplierPrice {
  supplierId: Id;
  productId: Id;
  price: number;
  updatedAt: IsoDate;
}

// ───────────────────────── Stock ─────────────────────────

/** A received batch of one product. Stock is FEFO (first expired, first out). */
export interface Lot {
  id: Id;
  productId: Id;
  supplierId?: Id;
  purchaseOrderId?: Id;
  qtyReceived: number;
  qtyRemaining: number;
  receivedAt: IsoDate;
  expiresAt: IsoDate;
}

export type StockMovementReason = "receipt" | "sale" | "adjustment" | "waste" | "return";

export interface StockMovement {
  id: Id;
  at: IsoDateTime;
  productId: Id;
  lotId?: Id;
  qty: number; // + in, - out
  reason: StockMovementReason;
  refType?: "order" | "purchase_order" | "manual";
  refId?: Id;
  note?: string;
}

/** Computed view, not stored. */
export interface StockLevel {
  productId: Id;
  onHand: number; // sum of lots remaining
  reserved: number; // confirmed/prepared orders not yet delivered
  available: number; // onHand - reserved
  incoming: number; // open purchase orders not yet received
  nextExpiry?: IsoDate;
  lots: Lot[];
}

// ───────────────────────── Sales ─────────────────────────

/**
 * draft     = pré-commande: captured (phone, voice, mail…), not committed yet
 * confirmed = accepted, stock reserved
 * prepared  = picked & weighed (preparedQty set)
 * delivered = left the warehouse and handed to the client; stock consumed (FEFO)
 * invoiced  = an invoice exists
 * cancelled
 */
export type OrderStatus = "draft" | "confirmed" | "prepared" | "delivered" | "invoiced" | "cancelled";
export type OrderSource = "phone" | "voice_agent" | "email" | "whatsapp" | "manual" | "web";

export interface OrderLine {
  id: Id;
  productId: Id;
  qty: number;
  unitPrice: number; // € HT, resolved from ClientPrice or Product.price at creation
  preparedQty?: number; // actual weight/quantity picked
  note?: string; // "bien frais", "sans tête"
  substituteFor?: Id; // productId this line replaces
}

export interface Order {
  id: Id;
  number: string; // "CMD-2026-000123"
  clientId: Id;
  status: OrderStatus;
  source: OrderSource;
  deliveryDate: IsoDate;
  routeRunId?: Id;
  lines: OrderLine[];
  totalHt: number; // computed on write
  note?: string;
  createdAt: IsoDateTime;
  createdBy: string; // "sophie" | "voice-agent" | ...
  confirmedAt?: IsoDateTime;
  deliveredAt?: IsoDateTime;
  invoiceId?: Id;
}

// ───────────────────────── Purchasing ─────────────────────────

export type PurchaseOrderStatus = "draft" | "sent" | "partially_received" | "received" | "cancelled";

export interface PurchaseOrderLine {
  id: Id;
  productId: Id;
  qty: number;
  unitPrice: number;
  receivedQty: number;
}

export interface PurchaseOrder {
  id: Id;
  number: string; // "ACH-2026-000045"
  supplierId: Id;
  status: PurchaseOrderStatus;
  expectedDate: IsoDate;
  lines: PurchaseOrderLine[];
  totalHt: number;
  createdAt: IsoDateTime;
  note?: string;
}

// ───────────────────────── Billing ─────────────────────────

/** issued → partially_paid → paid ; "overdue" is computed (issued/partially_paid past dueDate). */
export type InvoiceStatus = "draft" | "issued" | "partially_paid" | "paid" | "overdue" | "cancelled";

export interface InvoiceLine {
  productId: Id;
  label: string;
  qty: number;
  unitPrice: number;
  vatRate: number;
  totalHt: number;
}

export interface Invoice {
  id: Id;
  number: string; // "FAC-2026-000210"
  clientId: Id;
  orderIds: Id[];
  status: InvoiceStatus;
  issuedAt: IsoDate;
  dueDate: IsoDate;
  lines: InvoiceLine[];
  totalHt: number;
  totalVat: number;
  totalTtc: number;
  amountPaid: number;
}

export type PaymentMethod = "transfer" | "card" | "cheque" | "cash" | "direct_debit";

export interface PaymentAllocation {
  invoiceId: Id;
  amount: number;
}

export interface Payment {
  id: Id;
  clientId: Id;
  amount: number; // € TTC
  method: PaymentMethod;
  receivedAt: IsoDate;
  reference?: string;
  allocations: PaymentAllocation[];
}

// ───────────────────────── Logistics ─────────────────────────

/** A recurring delivery route (tournée). */
export interface Route {
  id: Id;
  name: string; // "Tournée Paris Ouest"
  zone: string;
  driver: string;
  vehicle: string; // "Camion frigo 12 m³"
  capacityKg: number;
  days: Weekday[];
  departureTime: string; // "05:30"
}

export type StopStatus = "pending" | "delivered" | "failed";

export interface RouteStop {
  orderId: Id;
  clientId: Id;
  seq: number;
  eta?: string; // "07:10"
  status: StopStatus;
  note?: string;
}

/** One route on one date. */
export interface RouteRun {
  id: Id;
  routeId: Id;
  date: IsoDate;
  status: "planned" | "in_progress" | "done";
  stops: RouteStop[];
}

// ───────────────────────── Activity ─────────────────────────

export type Actor = "user" | "ai_chat" | "voice_agent" | "system";

/** Every write appends one. Streamed live to the UI (SSE /api/events/stream). */
export interface ActivityEvent {
  id: Id;
  at: IsoDateTime;
  actor: Actor;
  actorName?: string;
  type: string; // "order.created", "order.confirmed", "payment.recorded", ...
  entity: "client" | "supplier" | "product" | "stock" | "order" | "purchase_order" | "invoice" | "payment" | "route_run" | "context";
  entityId: Id;
  summary: string; // French human sentence: "Commande CMD-… confirmée pour Le Bistrot du Port"
}

// ───────────────────────── Client history ─────────────────────────

/**
 * Long-term relationship history with a client (can span years): every complaint, return,
 * dispute, call, visit, negotiation… This is what makes a client a believable persona and
 * what a smart agent should know before speaking to them.
 */
export type ClientEventType =
  | "onboarding" // became a client / first order
  | "call" // notable phone call
  | "visit" // sales rep visit, tasting at the restaurant
  | "complaint" // generic complaint
  | "quality_issue" // product quality (freshness, caliber, smell…)
  | "delivery_issue" // late, missing items, wrong address, broken cold chain
  | "return" // goods sent back
  | "credit_note" // avoir granted
  | "dispute" // disagreement on weight, price, invoice
  | "late_payment" // payment incident, reminder, bounced cheque
  | "payment_plan" // agreed schedule to pay a debt
  | "price_negotiation" // new negotiated prices, discount request
  | "special_request" // event, custom cut, unusual product
  | "menu_change" // new chef, new menu, seasonal change → new needs
  | "contact_change" // new buyer, chef left, new manager
  | "compliment"
  | "churn_risk" // went to a competitor, ordering less
  | "won_back"
  | "note"; // anything else worth remembering

export type ClientEventChannel = "phone" | "email" | "whatsapp" | "visit" | "voice_agent" | "sms" | "other";

export interface ClientEvent {
  id: Id; // "cev_000123"
  clientId: Id;
  at: IsoDateTime;
  type: ClientEventType;
  title: string; // short French line: "Réclamation : langoustines arrivées mortes"
  description: string; // what happened, in plain French, can quote the client
  channel?: ClientEventChannel;
  author: string; // "Sophie (commerciale)", "Karim (direction)", "Agent vocal"
  severity?: "low" | "medium" | "high";
  status?: "open" | "resolved"; // for issues
  resolvedAt?: IsoDateTime;
  resolution?: string; // "Avoir de 84 € accordé, lot remplacé le lendemain"
  orderId?: Id;
  invoiceId?: Id;
  productIds?: Id[];
  amount?: number; // € involved (credit note, disputed amount, debt)
  tags?: string[];
}

/** Same idea for suppliers: the long-term history of our relationship with them. */
export type SupplierEventType =
  | "onboarding" // first purchase / listing
  | "call"
  | "visit" // visit at the auction, the farm, the boat
  | "quality_issue" // freshness, caliber, parasites, temperature on arrival
  | "delivery_issue" // late truck, short delivery, wrong products
  | "shortage" // no supply (storm, season, quota)
  | "return" // goods sent back to the supplier
  | "credit_note" // avoir received
  | "dispute" // weight, price, invoice disagreement
  | "price_change" // new price list, surcharge (fuel, storm)
  | "price_negotiation" // annual deal, volume discount
  | "invoice_issue" // wrong invoice, duplicate
  | "payment" // our own payment incident (we paid late, agreed delay)
  | "contract" // framework agreement, exclusivity, volume commitment
  | "certification" // label, audit, sanitary approval, MSC
  | "contact_change"
  | "compliment"
  | "note";

export interface SupplierEvent {
  id: Id; // "sev_000123"
  supplierId: Id;
  at: IsoDateTime;
  type: SupplierEventType;
  title: string;
  description: string;
  channel?: ClientEventChannel;
  author: string; // "Marc (achats)", "Karim (direction)"
  severity?: "low" | "medium" | "high";
  status?: "open" | "resolved";
  resolvedAt?: IsoDateTime;
  resolution?: string;
  purchaseOrderId?: Id;
  productIds?: Id[];
  amount?: number;
  tags?: string[];
}

// ───────────────────────── Groups (tags) & pricing ─────────────────────────

/** A group/tag definition. Entities carry tag ids in their `tags` array. */
export interface TagDef {
  id: string; // slug, unique per scope: "gastro", "premium"
  scope: "client" | "supplier" | "product";
  label: string; // "Restaurants gastronomiques"
  color?: "green" | "teal" | "amber" | "blue" | "rose" | "violet" | "gray";
  description?: string;
}

export type PriceRuleClientScope =
  | { kind: "all" }
  | { kind: "client"; clientId: Id }
  | { kind: "tag"; tag: string }; // client group

export type PriceRuleProductScope =
  | { kind: "all" }
  | { kind: "product"; productId: Id }
  | { kind: "tag"; tag: string } // product group
  | { kind: "category"; category: ProductCategory };

export type PriceRuleMethod =
  | { kind: "fixed"; price: number } // € HT per unit
  | { kind: "discount_pct"; pct: number } // % off the list price
  | { kind: "markup_pct"; pct: number }; // % on top of the product cost

/**
 * Pricing rule for a group of clients × a group of products.
 * Resolution (most specific wins, then higher priority, then most recent):
 *   1. ClientPrice (explicit negotiated price client × product)
 *   2. PriceRule client+product  >  client+tag/category  >  clientTag+product  >  clientTag+productTag/category  >  all-clients rules
 *   3. Product.price (list price)
 * Rules respect validity dates and minQty.
 */
export interface PriceRule {
  id: Id; // "prl_0001"
  name: string; // "Gastro : -8 % sur les crustacés"
  active: boolean;
  priority: number; // tie-breaker, higher wins
  clientScope: PriceRuleClientScope;
  productScope: PriceRuleProductScope;
  method: PriceRuleMethod;
  minQty?: number;
  validFrom?: IsoDate;
  validTo?: IsoDate;
  note?: string;
  createdAt: IsoDateTime;
}

// ───────────────────────── Context (what the agent should know) ─────────────────────────

/** Who/what a context entry is about. `category` entries use a ProductCategory as entityId. */
export type ContextScope = "company" | "client" | "supplier" | "product" | "category";

/**
 * Kind of knowledge:
 *  policy = a rule that must be respected ("no discount by the night desk")
 *  procedure = how to do / say something ("read the order back before hanging up")
 *  preference = what they like, buy, how they order
 *  fact = background, profile, open follow-up
 *  relationship = people, who talks to whom, how they speak
 *  pricing = agreements, discounts, negotiation
 *  logistics = delivery, cut-off times, storage, shelf life
 *  risk = irritants, credit, churn, what not to do
 */
export type ContextKind = "policy" | "procedure" | "preference" | "fact" | "relationship" | "pricing" | "logistics" | "risk";

/** Who wrote the entry: the data pack, a person in the UI, or an agent during a chat / call. */
export type ContextSource = "seed" | "user" | "ai_chat" | "voice_agent";

/**
 * One context fact for the agents: a short, editable, queryable piece of business knowledge
 * (company rules, a client's habits and people, a supplier's negotiation style, product aliases…).
 * Built from the markdown in the data pack's context/ folder; agents can add their own (save_context).
 */
export interface ContextEntry {
  id: Id; // "ctx_0001"
  entityType: ContextScope;
  entityId?: Id; // cli_…, sup_…, prd_… or a ProductCategory; absent for scope "company"
  kind: ContextKind;
  title: string; // short French title: "Comment leur parler"
  body: string; // short markdown
  tags?: string[]; // free keywords: ["substitution", "dossier-ouvert"]
  source?: ContextSource;
  createdAt: IsoDateTime;
  updatedAt: IsoDateTime;
}

// ───────────────────────── Data pack ─────────────────────────

/** Shape of the JSON files in the data repo (one file per key, e.g. clients.json). */
export interface DataPack {
  meta: { company: string; today: IsoDate; currency: "EUR"; generatedAt: IsoDateTime; trade?: string; region?: string; categories?: Category[] };
  products: Product[];
  clients: Client[];
  clientPrices: ClientPrice[];
  suppliers: Supplier[];
  supplierPrices: SupplierPrice[];
  lots: Lot[];
  stockMovements: StockMovement[];
  orders: Order[];
  purchaseOrders: PurchaseOrder[];
  invoices: Invoice[];
  payments: Payment[];
  routes: Route[];
  routeRuns: RouteRun[];
  clientEvents: ClientEvent[];
  supplierEvents: SupplierEvent[];
  tags: TagDef[];
  priceRules: PriceRule[];
  contextEntries: ContextEntry[];
}
