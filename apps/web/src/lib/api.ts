/**
 * Typed client for the ERP API (packages/shared/src/api.ts). One function per route.
 * Base path /api (proxied by Vite to http://localhost:4000).
 * Errors: throws ApiRequestError AND shows a toast (pass {silent:true} to opt out on reads you handle yourself).
 * Every write is sent with x-actor: user (the voice agent / AI chat set their own actor server-side).
 */
import type {
  ActivityEvent, Client, ClientDetail, ClientInput, ClientSummary, Dashboard, DataPack, Id, InvoiceDetail,
  InvoiceSummary, IsoDate, OrderDetail, OrderInput, OrderLineInput, OrderStatus, PaymentInput, PaymentSummary,
  ProductCategory, ProductDetail, ProductSummary, PurchaseOrderDetail, PurchaseOrderInput, PurchaseOrderStatus,
  Route, RouteRunDetail, SearchResult, StockLevel, StockMovement, Supplier, SupplierDetail, UsualBasketLine,
  InvoiceStatus, ClientType, Product, OrderSummary, PurchaseOrderSummary,
} from "@kit/shared";
import type {
  ClientEvent, ClientEventInput, ClientEventSummary, SupplierEvent, SupplierEventInput, SupplierEventSummary,
} from "@kit/shared";
import type {
  ClientPrice, PriceGridRow, PriceRule, PriceRuleInput, PriceRuleSummary, ResolvedPrice, TagDef,
} from "@kit/shared";
import type { Receivables } from "@kit/shared";
import type { Category } from "@kit/shared";
import type { ContextEntry, ContextEntryInput, ContextEntrySummary, ContextForEntity, ContextScope } from "@kit/shared";
import type { ListParams, Page } from "@kit/shared";
import { toast } from "@/ui/toast";

export const API_BASE = "/api";
export const AI_BASE = "/ai";

export class ApiRequestError extends Error {
  constructor(public status: number, public code: string, message: string) {
    super(message);
  }
}

type Query = Record<string, string | number | boolean | undefined | null | string[]>;
interface ReqOpts { silent?: boolean; signal?: AbortSignal }

function qs(params?: Query): string {
  if (!params) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === "") continue;
    sp.set(k, Array.isArray(v) ? v.join(",") : String(v));
  }
  const s = sp.toString();
  return s ? `?${s}` : "";
}

async function request<T>(method: string, path: string, body?: unknown, opts: ReqOpts = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method,
      headers: {
        ...(body !== undefined ? { "content-type": "application/json" } : {}),
        ...(method !== "GET" ? { "x-actor": "user", "x-actor-name": "Moi" } : {}),
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: opts.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") throw e;
    const err = new ApiRequestError(0, "network", "API injoignable (localhost:4000)");
    if (!opts.silent) toast.error("Connexion impossible", err.message);
    throw err;
  }
  if (!res.ok) {
    let code = `http_${res.status}`;
    let message = res.statusText || "Erreur";
    try {
      const j = await res.json();
      if (j?.error) ({ code, message } = j.error);
    } catch { /* not JSON */ }
    const err = new ApiRequestError(res.status, code, message);
    if (!opts.silent) toast.error(method === "GET" ? "Chargement impossible" : "Action refusée", message);
    throw err;
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const get = <T>(path: string, params?: Query, opts?: ReqOpts) => request<T>("GET", `${path}${qs(params)}`, undefined, opts);
/** One page of a list route, with its total and extras (`?envelope=1`, see TECH.md « Pagination »). */
const getPage = <T>(path: string, params?: object, opts?: ReqOpts) => get<Page<T>>(path, { ...(params as Query), envelope: 1 }, opts);
/** Max rows of one list call: reference tables (clients, products, suppliers) are small and loaded whole for pickers. */
export const LIST_MAX = 500;
const whole = <P extends object>(p?: P) => ({ limit: LIST_MAX, ...(p ?? {}) }) as Query;
const post = <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {});
const patch = <T>(path: string, body: unknown) => request<T>("PATCH", path, body);
const del = <T>(path: string) => request<T>("DELETE", path);

// ── Params (every list also takes ListParams: limit / offset / sort / order) ──
export type { ListParams, Page };
export interface ClientListParams extends ListParams { q?: string; type?: ClientType | ""; zone?: string; status?: Client["status"] | ""; tag?: string }
export interface SupplierListParams extends ListParams { q?: string; category?: ProductCategory | ""; tag?: string }
export interface ProductListParams extends ListParams { q?: string; category?: ProductCategory | ""; tag?: string; active?: boolean }
export interface StockListParams extends ListParams { q?: string; tab?: "out" | "low" | "expiring" | "" }
export interface MovementListParams extends ListParams { productId?: Id }
/** status: comma list. */
export interface OrderListParams extends ListParams { status?: OrderStatus | string; clientId?: Id; date?: IsoDate; q?: string; source?: string; ids?: string }
export interface PurchaseOrderListParams extends ListParams { status?: PurchaseOrderStatus | string; supplierId?: Id; date?: IsoDate; q?: string }
/** status: comma list of effective statuses (overdue computed) or the pseudo-status "open" (unpaid balance). */
export interface InvoiceListParams extends ListParams { status?: InvoiceStatus | "open" | string; clientId?: Id; q?: string }
export interface PaymentListParams extends ListParams { clientId?: Id; method?: string; q?: string }
export interface ActivityListParams extends ListParams { actor?: string; entity?: string }
export type SearchType = SearchResult["type"];
/** History (client / supplier events). `type` = comma-separated event types. */
export interface EntityEventParams extends ListParams { type?: string; status?: "open" | "resolved" | ""; q?: string }
export interface EventSearchParams extends ListParams { type?: string; status?: "open" | "resolved" | ""; q?: string; from?: IsoDate; to?: IsoDate }
export type EventPatch<I> = Partial<I> & { status?: "open" | "resolved"; resolution?: string };
export type TagScope = TagDef["scope"];
export type TagWithCount = TagDef & { count: number };
/** Encours (aged balance). */
export interface ReceivablesParams { q?: string; tag?: string; rep?: string; zone?: string; onlyOverdue?: boolean }
/** Contexte: scope / kind / source may be comma-separated. */
export interface ContextListParams extends ListParams { entityType?: string; entityId?: Id; kind?: string; source?: string; tag?: string; q?: string }
export interface PriceGridParams { clientId?: Id; clientTag?: string; productTag?: string; category?: ProductCategory | ""; q?: string }

export const api = {
  health: () => get<{ ok: boolean }>("/health", undefined, { silent: true }),
  meta: () => get<DataPack["meta"]>("/meta"),
  categories: () => get<Category[]>("/categories"),
  dashboard: () => get<Dashboard>("/dashboard"),
  search: (q: string, types?: SearchType[], opts?: ReqOpts) => get<SearchResult[]>("/search", { q, types }, { silent: true, ...opts }),

  clients: {
    /** Whole list (≤ LIST_MAX) — pickers / lookups. */
    list: (p?: ClientListParams) => get<ClientSummary[]>("/clients", whole(p)),
    page: (p?: ClientListParams) => getPage<ClientSummary>("/clients", p),
    get: (id: Id) => get<ClientDetail>(`/clients/${id}`),
    usual: (id: Id) => get<UsualBasketLine[]>(`/clients/${id}/usual`),
    create: (body: ClientInput) => post<Client>("/clients", body),
    update: (id: Id, body: Partial<ClientInput>) => patch<Client>(`/clients/${id}`, body),
    addNote: (id: Id, body: { text: string; author: string }) => post<Client>(`/clients/${id}/notes`, body),
  },

  suppliers: {
    list: (p?: SupplierListParams) => get<Supplier[]>("/suppliers", whole(p)),
    get: (id: Id) => get<SupplierDetail>(`/suppliers/${id}`),
    usual: (id: Id) => get<UsualBasketLine[]>(`/suppliers/${id}/usual`),
  },

  products: {
    /** Whole catalogue (≤ LIST_MAX) — pickers / lookups. */
    list: (p?: ProductListParams) => get<ProductSummary[]>("/products", whole(p)),
    page: (p?: ProductListParams) => getPage<ProductSummary>("/products", p),
    get: (id: Id) => get<ProductDetail>(`/products/${id}`),
    alternatives: (id: Id) => get<ProductSummary[]>(`/products/${id}/alternatives`),
  },

  stock: {
    page: (p?: StockListParams) => getPage<StockLevel & { product: Product }>("/stock", p),
    movements: (p?: MovementListParams) => getPage<StockMovement>("/stock/movements", p),
    adjust: (body: { productId: Id; qty: number; reason: "adjustment" | "waste"; note?: string }) => post<StockLevel>("/stock/adjust", body),
  },

  orders: {
    list: (p?: OrderListParams) => get<OrderSummary[]>("/orders", p as Query),
    page: (p?: OrderListParams) => getPage<OrderSummary>("/orders", p),
    get: (id: Id) => get<OrderDetail>(`/orders/${id}`),
    create: (body: OrderInput) => post<OrderDetail>("/orders", body),
    update: (id: Id, body: { deliveryDate?: IsoDate; note?: string }) => patch<OrderDetail>(`/orders/${id}`, body),
    addLine: (id: Id, body: OrderLineInput) => post<OrderDetail>(`/orders/${id}/lines`, body),
    updateLine: (id: Id, lineId: Id, body: Partial<OrderLineInput> & { preparedQty?: number }) => patch<OrderDetail>(`/orders/${id}/lines/${lineId}`, body),
    removeLine: (id: Id, lineId: Id) => del<OrderDetail>(`/orders/${id}/lines/${lineId}`),
    confirm: (id: Id) => post<OrderDetail>(`/orders/${id}/confirm`),
    prepare: (id: Id, body?: { lines?: { lineId: Id; preparedQty: number }[] }) => post<OrderDetail>(`/orders/${id}/prepare`, body),
    deliver: (id: Id) => post<OrderDetail>(`/orders/${id}/deliver`),
    invoice: (id: Id) => post<InvoiceDetail>(`/orders/${id}/invoice`),
    cancel: (id: Id) => post<OrderDetail>(`/orders/${id}/cancel`),
  },

  purchaseOrders: {
    page: (p?: PurchaseOrderListParams) => getPage<PurchaseOrderSummary>("/purchase-orders", p),
    get: (id: Id) => get<PurchaseOrderDetail>(`/purchase-orders/${id}`),
    create: (body: PurchaseOrderInput) => post<PurchaseOrderDetail>("/purchase-orders", body),
    update: (id: Id, body: { expectedDate?: IsoDate; note?: string }) => patch<PurchaseOrderDetail>(`/purchase-orders/${id}`, body),
    addLine: (id: Id, body: { productId: Id; qty: number; unitPrice?: number }) => post<PurchaseOrderDetail>(`/purchase-orders/${id}/lines`, body),
    updateLine: (id: Id, lineId: Id, body: { qty?: number; unitPrice?: number; productId?: Id }) => patch<PurchaseOrderDetail>(`/purchase-orders/${id}/lines/${lineId}`, body),
    removeLine: (id: Id, lineId: Id) => del<PurchaseOrderDetail>(`/purchase-orders/${id}/lines/${lineId}`),
    send: (id: Id) => post<PurchaseOrderDetail>(`/purchase-orders/${id}/send`),
    receive: (id: Id, body?: { lines?: { lineId: Id; receivedQty: number }[] }) => post<PurchaseOrderDetail>(`/purchase-orders/${id}/receive`, body),
    cancel: (id: Id) => post<PurchaseOrderDetail>(`/purchase-orders/${id}/cancel`),
  },

  invoices: {
    list: (p?: InvoiceListParams) => get<InvoiceSummary[]>("/invoices", p as Query),
    page: (p?: InvoiceListParams) => getPage<InvoiceSummary>("/invoices", p),
    get: (id: Id) => get<InvoiceDetail>(`/invoices/${id}`),
  },

  receivables: {
    get: (p?: ReceivablesParams) => get<Receivables>("/receivables", p as Query),
  },

  payments: {
    page: (p?: PaymentListParams) => getPage<PaymentSummary>("/payments", p),
    create: (body: PaymentInput) => post<PaymentSummary>("/payments", body),
  },

  routes: {
    list: () => get<Route[]>("/routes"),
  },

  routeRuns: {
    list: (p?: { date?: IsoDate }) => get<RouteRunDetail[]>("/route-runs", p as Query),
    plan: (date: IsoDate) => post<RouteRunDetail[]>("/route-runs/plan", { date }),
    reorderStops: (id: Id, orderIds: Id[]) => patch<RouteRunDetail>(`/route-runs/${id}/stops`, { orderIds }),
  },

  events: {
    list: (p?: { limit?: number }) => get<ActivityEvent[]>("/events", p as Query),
    page: (p?: ActivityListParams) => getPage<ActivityEvent>("/events", p),
    streamUrl: `${API_BASE}/events/stream`,
  },

  // ── Groups (tags) & pricing ──
  tags: {
    list: (scope?: TagScope) => get<TagWithCount[]>("/tags", { scope }),
    create: (body: TagDef) => post<TagDef>("/tags", body),
    update: (scope: TagScope, id: string, body: Partial<Pick<TagDef, "label" | "color" | "description">>) =>
      patch<TagDef>(`/tags/${scope}/${id}`, body),
    remove: (scope: TagScope, id: string) => del<{ ok: true }>(`/tags/${scope}/${id}`),
    /** Entities of one scope carrying a tag (list endpoints with ?tag=). */
    members: (scope: TagScope, tag: string) =>
      scope === "client" ? get<ClientSummary[]>("/clients", whole({ tag }))
      : scope === "product" ? get<ProductSummary[]>("/products", whole({ tag }))
      : get<Supplier[]>("/suppliers", whole({ tag })),
    /** Replace the tags of one client / product / supplier. */
    setOn: (scope: TagScope, entityId: Id, tags: string[]) =>
      patch<unknown>(`/${scope === "client" ? "clients" : scope === "product" ? "products" : "suppliers"}/${entityId}`, { tags }),
  },

  priceRules: {
    list: (p?: { active?: boolean; clientId?: Id; productId?: Id }) => get<PriceRuleSummary[]>("/price-rules", whole(p)),
    create: (body: PriceRuleInput) => post<PriceRule>("/price-rules", body),
    update: (id: Id, body: Partial<PriceRuleInput>) => patch<PriceRule>(`/price-rules/${id}`, body),
    remove: (id: Id) => del<{ ok: true }>(`/price-rules/${id}`),
  },

  prices: {
    resolve: (p: { clientId: Id; productId: Id; qty?: number; date?: IsoDate }, opts?: ReqOpts) =>
      get<ResolvedPrice>("/prices/resolve", p as Query, opts),
    grid: (p: PriceGridParams) => get<PriceGridRow[]>("/prices/grid", p as Query),
    setClientPrice: (clientId: Id, productId: Id, price: number) =>
      request<ClientPrice>("PUT", `/clients/${clientId}/prices/${productId}`, { price }),
    removeClientPrice: (clientId: Id, productId: Id) => del<{ ok: true }>(`/clients/${clientId}/prices/${productId}`),
  },

  // ── History: long-term client / supplier events ──
  clientEvents: {
    /** One client's history (≤ LIST_MAX, newest first) — filtered on the page. */
    list: (clientId: Id, p?: EntityEventParams) => get<ClientEventSummary[]>(`/clients/${clientId}/events`, whole(p)),
    search: (p?: EventSearchParams & { clientId?: Id }) => getPage<ClientEventSummary>("/client-events", p),
    create: (clientId: Id, body: ClientEventInput) => post<ClientEvent>(`/clients/${clientId}/events`, body),
    update: (id: Id, body: EventPatch<ClientEventInput>) => patch<ClientEvent>(`/client-events/${id}`, body),
  },
  supplierEvents: {
    list: (supplierId: Id, p?: EntityEventParams) => get<SupplierEventSummary[]>(`/suppliers/${supplierId}/events`, whole(p)),
    search: (p?: EventSearchParams & { supplierId?: Id }) => getPage<SupplierEventSummary>("/supplier-events", p),
    create: (supplierId: Id, body: SupplierEventInput) => post<SupplierEvent>(`/suppliers/${supplierId}/events`, body),
    update: (id: Id, body: EventPatch<SupplierEventInput>) => patch<SupplierEvent>(`/supplier-events/${id}`, body),
  },

  // ── Context table (what the agents know) ──
  context: {
    list: (p?: ContextListParams) => get<ContextEntrySummary[]>("/context", p as Query),
    page: (p?: ContextListParams) => getPage<ContextEntrySummary>("/context", p),
    get: (id: Id) => get<ContextEntrySummary>(`/context/${id}`),
    for: (scope: ContextScope, id: Id) => get<ContextForEntity>("/context/for", { entityType: scope, id }),
    create: (body: ContextEntryInput) => post<ContextEntry>("/context", body),
    update: (id: Id, body: Partial<ContextEntryInput>) => patch<ContextEntry>(`/context/${id}`, body),
    remove: (id: Id) => del<{ ok: true }>(`/context/${id}`),
  },

  admin: {
    reset: () => post<{ ok: true }>("/admin/reset"),
  },
};

export type Api = typeof api;
