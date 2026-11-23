/**
 * React Query layer: query keys, one hook per read route, a mutation helper, and the live SSE stream.
 *
 *   const { data, isLoading } = useClients({ q, type });
 *   const confirm = useApiMutation(api.orders.confirm, { success: "Commande confirmée", invalidate: [qk.orders.all] });
 *   confirm.mutate(order.id);
 *
 * Live updates: <ActivityStreamProvider/> (mounted once in the shell) opens /api/events/stream and, on every
 * ActivityEvent, invalidates the queries of the touched entity (see INVALIDATE). So when the voice agent writes,
 * every visible list/detail refetches by itself. Pages never need to poll.
 */
import { useEffect, useSyncExternalStore } from "react";
import {
  keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient, type QueryKey,
} from "@tanstack/react-query";
import type { ActivityEvent, Id, IsoDate } from "@kit/shared";
import {
  api, type ActivityListParams, type ClientListParams, type InvoiceListParams, type MovementListParams, type OrderListParams,
  type Page, type PaymentListParams, type ProductListParams, type PurchaseOrderListParams, type SearchType, type StockListParams,
  type SupplierListParams,
} from "./api";
import type { EntityEventParams, EventSearchParams } from "./api";
import type { PriceGridParams, TagScope } from "./api";
import type { ReceivablesParams } from "./api";
import type { ContextListParams } from "./api";
import type { ContextScope } from "@kit/shared";
import { toast } from "@/ui/toast";
import { setBusinessToday } from "./clock";
import { setCategories } from "./labels";

// ── Query keys (prefix-based: invalidating qk.orders.all refreshes every orders list + detail) ──
export const qk = {
  meta: ["meta"] as const,
  categories: ["categories"] as const,
  dashboard: ["dashboard"] as const,
  search: (q: string, types?: SearchType[]) => ["search", q, types ?? []] as const,
  clients: {
    all: ["clients"] as const,
    list: (p?: ClientListParams) => ["clients", "list", p ?? {}] as const,
    page: (p?: ClientListParams) => ["clients", "page", p ?? {}] as const,
    detail: (id: Id) => ["clients", "detail", id] as const,
    usual: (id: Id) => ["clients", "usual", id] as const,
    /** Encours: under the clients root so client / order / invoice / payment events refresh it. */
    receivables: (p?: ReceivablesParams) => ["clients", "receivables", p ?? {}] as const,
  },
  suppliers: {
    all: ["suppliers"] as const,
    list: (p?: SupplierListParams) => ["suppliers", "list", p ?? {}] as const,
    detail: (id: Id) => ["suppliers", "detail", id] as const,
    usual: (id: Id) => ["suppliers", "usual", id] as const,
  },
  products: {
    all: ["products"] as const,
    list: (p?: ProductListParams) => ["products", "list", p ?? {}] as const,
    page: (p?: ProductListParams) => ["products", "page", p ?? {}] as const,
    detail: (id: Id) => ["products", "detail", id] as const,
    alternatives: (id: Id) => ["products", "alternatives", id] as const,
  },
  stock: {
    all: ["stock"] as const,
    page: (p?: StockListParams) => ["stock", "page", p ?? {}] as const,
    movements: (p?: MovementListParams) => ["stock", "movements", p ?? {}] as const,
  },
  orders: {
    all: ["orders"] as const,
    list: (p?: OrderListParams) => ["orders", "list", p ?? {}] as const,
    page: (p?: OrderListParams) => ["orders", "page", p ?? {}] as const,
    detail: (id: Id) => ["orders", "detail", id] as const,
  },
  purchaseOrders: {
    all: ["purchase-orders"] as const,
    page: (p?: PurchaseOrderListParams) => ["purchase-orders", "page", p ?? {}] as const,
    detail: (id: Id) => ["purchase-orders", "detail", id] as const,
  },
  invoices: {
    all: ["invoices"] as const,
    list: (p?: InvoiceListParams) => ["invoices", "list", p ?? {}] as const,
    page: (p?: InvoiceListParams) => ["invoices", "page", p ?? {}] as const,
    detail: (id: Id) => ["invoices", "detail", id] as const,
  },
  payments: {
    all: ["payments"] as const,
    page: (p?: PaymentListParams) => ["payments", "page", p ?? {}] as const,
  },
  routes: { all: ["routes"] as const },
  routeRuns: {
    all: ["route-runs"] as const,
    list: (p?: { date?: IsoDate }) => ["route-runs", "list", p ?? {}] as const,
  },
  tags: {
    all: ["tags"] as const,
    list: (scope?: TagScope) => ["tags", "list", scope ?? "all"] as const,
    members: (scope: TagScope, tag: string) => ["tags", "members", scope, tag] as const,
  },
  pricing: {
    all: ["pricing"] as const,
    rules: (p?: object) => ["pricing", "rules", p ?? {}] as const,
    grid: (p: PriceGridParams) => ["pricing", "grid", p] as const,
    resolve: (p: object) => ["pricing", "resolve", p] as const,
    negotiated: () => ["pricing", "negotiated"] as const,
  },
  events: {
    all: ["events"] as const,
    list: (limit = 100) => ["events", "list", limit] as const,
    page: (p?: ActivityListParams) => ["events", "page", p ?? {}] as const,
  },
  /** Context table: the list page and the per-entity sections. */
  context: {
    all: ["context"] as const,
    list: (p?: ContextListParams) => ["context", "list", p ?? {}] as const,
    page: (p?: ContextListParams) => ["context", "page", p ?? {}] as const,
    for: (scope: ContextScope, id: Id) => ["context", "for", scope, id] as const,
  },
  /** Long-term history. Per-entity lists live under clients/suppliers (refreshed with them); company-wide under "history". */
  history: {
    all: ["history"] as const,
    client: (id: Id, p?: EntityEventParams) => ["clients", "events", id, p ?? {}] as const,
    supplier: (id: Id, p?: EntityEventParams) => ["suppliers", "events", id, p ?? {}] as const,
    clientSearch: (p?: EventSearchParams) => ["history", "clients", p ?? {}] as const,
    supplierSearch: (p?: EventSearchParams) => ["history", "suppliers", p ?? {}] as const,
  },
};

const clean = <T extends object>(p?: T) =>
  p ? (Object.fromEntries(Object.entries(p).filter(([, v]) => v !== undefined && v !== "" && v !== null)) as T) : undefined;

// ── Read hooks ──
export const useMeta = () =>
  useQuery({ queryKey: qk.meta, queryFn: () => api.meta().then((m) => (setBusinessToday(m.today), m)), staleTime: Infinity });
/** Product categories of the company ({id, label}); also refreshes the label map used by categoryLabel(). */
export const useCategories = () =>
  useQuery({ queryKey: qk.categories, queryFn: () => api.categories().then((c) => (setCategories(c), c)), staleTime: Infinity });
export const useDashboard = () => useQuery({ queryKey: qk.dashboard, queryFn: api.dashboard });
export const useSearch = (q: string, types?: SearchType[]) =>
  useQuery({ queryKey: qk.search(q, types), queryFn: ({ signal }) => api.search(q, types, { signal }), enabled: q.trim().length > 0, placeholderData: keepPreviousData });

/** Whole client list (≤ LIST_MAX) for pickers and lookups. List pages use useClientsPage. */
export const useClients = (p?: ClientListParams) =>
  useQuery({ queryKey: qk.clients.list(clean(p)), queryFn: () => api.clients.list(clean(p)), placeholderData: keepPreviousData });
/** One server page ({ items, total, counts, facets }). */
export const useClientsPage = (p?: ClientListParams) =>
  useQuery({ queryKey: qk.clients.page(clean(p)), queryFn: () => api.clients.page(clean(p)), placeholderData: keepPreviousData });
export const useClient = (id?: Id) => useQuery({ queryKey: qk.clients.detail(id!), queryFn: () => api.clients.get(id!), enabled: !!id });
export const useClientUsual = (id?: Id) => useQuery({ queryKey: qk.clients.usual(id!), queryFn: () => api.clients.usual(id!), enabled: !!id });

export const useReceivables = (p?: ReceivablesParams) =>
  useQuery({ queryKey: qk.clients.receivables(clean(p)), queryFn: () => api.receivables.get(clean(p)), placeholderData: keepPreviousData });

export const useSuppliers = (p?: SupplierListParams) =>
  useQuery({ queryKey: qk.suppliers.list(clean(p)), queryFn: () => api.suppliers.list(clean(p)), placeholderData: keepPreviousData });
export const useSupplier = (id?: Id) => useQuery({ queryKey: qk.suppliers.detail(id!), queryFn: () => api.suppliers.get(id!), enabled: !!id });
export const useSupplierUsual = (id?: Id) => useQuery({ queryKey: qk.suppliers.usual(id!), queryFn: () => api.suppliers.usual(id!), enabled: !!id });

/** Whole catalogue (≤ LIST_MAX) for pickers and lookups. The Produits page uses useProductsPage. */
export const useProducts = (p?: ProductListParams) =>
  useQuery({ queryKey: qk.products.list(clean(p)), queryFn: () => api.products.list(clean(p)), placeholderData: keepPreviousData });
export const useProductsPage = (p?: ProductListParams) =>
  useQuery({ queryKey: qk.products.page(clean(p)), queryFn: () => api.products.page(clean(p)), placeholderData: keepPreviousData });
export const useProduct = (id?: Id) => useQuery({ queryKey: qk.products.detail(id!), queryFn: () => api.products.get(id!), enabled: !!id });
export const useProductAlternatives = (id?: Id) =>
  useQuery({ queryKey: qk.products.alternatives(id!), queryFn: () => api.products.alternatives(id!), enabled: !!id });

export const useStockPage = (p?: StockListParams) =>
  useQuery({ queryKey: qk.stock.page(clean(p)), queryFn: () => api.stock.page(clean(p)), placeholderData: keepPreviousData });
export const useStockMovements = (p?: MovementListParams) =>
  useQuery({ queryKey: qk.stock.movements(clean(p)), queryFn: () => api.stock.movements(clean(p)), placeholderData: keepPreviousData });

/** A bounded array (`limit`, default 100) — e.g. the latest orders of a client. List pages use useOrdersPage. */
export const useOrders = (p?: OrderListParams, enabled = true) =>
  useQuery({ queryKey: qk.orders.list(clean(p)), queryFn: () => api.orders.list(clean(p)), enabled, placeholderData: keepPreviousData });
export const useOrdersPage = (p?: OrderListParams) =>
  useQuery({ queryKey: qk.orders.page(clean(p)), queryFn: () => api.orders.page(clean(p)), placeholderData: keepPreviousData });
export const useOrder = (id?: Id) => useQuery({ queryKey: qk.orders.detail(id!), queryFn: () => api.orders.get(id!), enabled: !!id });

export const usePurchaseOrdersPage = (p?: PurchaseOrderListParams) =>
  useQuery({ queryKey: qk.purchaseOrders.page(clean(p)), queryFn: () => api.purchaseOrders.page(clean(p)), placeholderData: keepPreviousData });
export const usePurchaseOrder = (id?: Id) =>
  useQuery({ queryKey: qk.purchaseOrders.detail(id!), queryFn: () => api.purchaseOrders.get(id!), enabled: !!id });

/** A bounded array (`limit`, default 100). List pages use useInvoicesPage. */
export const useInvoices = (p?: InvoiceListParams, enabled = true) =>
  useQuery({ queryKey: qk.invoices.list(clean(p)), queryFn: () => api.invoices.list(clean(p)), enabled, placeholderData: keepPreviousData });
export const useInvoicesPage = (p?: InvoiceListParams) =>
  useQuery({ queryKey: qk.invoices.page(clean(p)), queryFn: () => api.invoices.page(clean(p)), placeholderData: keepPreviousData });
export const useInvoice = (id?: Id) => useQuery({ queryKey: qk.invoices.detail(id!), queryFn: () => api.invoices.get(id!), enabled: !!id });

export const usePaymentsPage = (p?: PaymentListParams) =>
  useQuery({ queryKey: qk.payments.page(clean(p)), queryFn: () => api.payments.page(clean(p)), placeholderData: keepPreviousData });

export const useRoutes = () => useQuery({ queryKey: qk.routes.all, queryFn: api.routes.list, staleTime: 60_000 });
export const useRouteRuns = (p?: { date?: IsoDate }) =>
  useQuery({ queryKey: qk.routeRuns.list(clean(p)), queryFn: () => api.routeRuns.list(clean(p)) });

// Groups (tags) & pricing
export const useTags = (scope?: TagScope) =>
  useQuery({ queryKey: qk.tags.list(scope), queryFn: () => api.tags.list(scope), staleTime: 30_000 });
export const useTagMembers = (scope: TagScope, tag?: string) =>
  useQuery<unknown[]>({ queryKey: qk.tags.members(scope, tag!), queryFn: () => api.tags.members(scope, tag!) as Promise<unknown[]>, enabled: !!tag });
export const usePriceRules = (p?: { active?: boolean; clientId?: Id; productId?: Id }) =>
  useQuery({ queryKey: qk.pricing.rules(clean(p)), queryFn: () => api.priceRules.list(clean(p)), placeholderData: keepPreviousData });
export const usePriceGrid = (p: PriceGridParams) =>
  useQuery({
    queryKey: qk.pricing.grid(clean(p)!), queryFn: () => api.prices.grid(clean(p)!),
    enabled: !!(p.clientId || p.clientTag), placeholderData: keepPreviousData,
  });
export const useResolvedPrice = (p: { clientId?: Id; productId?: Id; qty?: number; date?: IsoDate }, enabled = true) =>
  useQuery({
    queryKey: qk.pricing.resolve(clean(p)!),
    queryFn: () => api.prices.resolve(clean(p) as { clientId: Id; productId: Id; qty?: number; date?: IsoDate }, { silent: true }),
    enabled: enabled && !!p.clientId && !!p.productId && (p.qty === undefined || p.qty > 0),
    placeholderData: keepPreviousData,
  });

export const useEvents = (limit = 100) => useQuery({ queryKey: qk.events.list(limit), queryFn: () => api.events.list({ limit }) });
export const useEventsPage = (p?: ActivityListParams) =>
  useQuery({ queryKey: qk.events.page(clean(p)), queryFn: () => api.events.page(clean(p)), placeholderData: keepPreviousData });

// History (client / supplier events)
export const useClientEvents = (id?: Id, p?: EntityEventParams) =>
  useQuery({ queryKey: qk.history.client(id!, clean(p)), queryFn: () => api.clientEvents.list(id!, clean(p)), enabled: !!id, placeholderData: keepPreviousData });
export const useSupplierEvents = (id?: Id, p?: EntityEventParams) =>
  useQuery({ queryKey: qk.history.supplier(id!, clean(p)), queryFn: () => api.supplierEvents.list(id!, clean(p)), enabled: !!id, placeholderData: keepPreviousData });
export const useClientEventSearch = (p?: EventSearchParams, enabled = true) =>
  useQuery({ queryKey: qk.history.clientSearch(clean(p)), queryFn: () => api.clientEvents.search(clean(p)), enabled, placeholderData: keepPreviousData });
export const useSupplierEventSearch = (p?: EventSearchParams, enabled = true) =>
  useQuery({ queryKey: qk.history.supplierSearch(clean(p)), queryFn: () => api.supplierEvents.search(clean(p)), enabled, placeholderData: keepPreviousData });

// ── Mutations ──
/**
 * Wraps an api write. Errors already toast inside api.ts. On success: optional toast + invalidations.
 * Business warnings (OrderDetail.warnings) are toasted as warnings automatically.
 */
export function useApiMutation<TVars, TData>(
  fn: (vars: TVars) => Promise<TData>,
  opts: { success?: string | ((d: TData) => string); invalidate?: QueryKey[]; onSuccess?: (d: TData, v: TVars) => void } = {},
) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: (data, vars) => {
      const msg = typeof opts.success === "function" ? opts.success(data) : opts.success;
      if (msg) toast.success(msg);
      const warnings = (data as { warnings?: { message: string }[] } | undefined)?.warnings;
      warnings?.forEach((w) => toast.warning("Attention", w.message));
      opts.invalidate?.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      opts.onSuccess?.(data, vars);
    },
  });
}

export const useContextList = (p?: ContextListParams) =>
  useQuery({ queryKey: qk.context.list(clean(p)), queryFn: () => api.context.list(clean(p)), placeholderData: keepPreviousData });
export const useContextPage = (p?: ContextListParams) =>
  useQuery({ queryKey: qk.context.page(clean(p)), queryFn: () => api.context.page(clean(p)), placeholderData: keepPreviousData });
export const useContextEntry = (id?: Id) =>
  useQuery({ queryKey: [...qk.context.all, "one", id] as const, queryFn: () => api.context.get(id!), enabled: !!id });
export const useContextFor = (scope: ContextScope, id?: Id) =>
  useQuery({ queryKey: qk.context.for(scope, id!), queryFn: () => api.context.for(scope, id!), enabled: !!id });

// ── Live activity stream (SSE) ──
/** Which query roots to refresh when an entity changes. Add a line when you add an entity/page. */
export const INVALIDATE: Record<ActivityEvent["entity"], QueryKey[]> = {
  client: [qk.clients.all, qk.dashboard, qk.tags.all, qk.pricing.all, qk.history.all],
  supplier: [qk.suppliers.all, qk.tags.all, qk.history.all],
  product: [qk.products.all, qk.stock.all, qk.tags.all, qk.pricing.all],
  stock: [qk.stock.all, qk.products.all, qk.dashboard],
  order: [qk.orders.all, qk.clients.all, qk.stock.all, qk.products.all, qk.routeRuns.all, qk.invoices.all, qk.dashboard],
  purchase_order: [qk.purchaseOrders.all, qk.stock.all, qk.products.all, qk.suppliers.all, qk.dashboard],
  invoice: [qk.invoices.all, qk.orders.all, qk.clients.all, qk.payments.all, qk.dashboard],
  payment: [qk.payments.all, qk.invoices.all, qk.clients.all, qk.dashboard],
  route_run: [qk.routeRuns.all, qk.orders.all],
  context: [qk.context.all],
};

export type StreamStatus = "connecting" | "live" | "offline";
let streamStatus: StreamStatus = "connecting";
const statusListeners = new Set<() => void>();
const activityListeners = new Set<(e: ActivityEvent) => void>();
/** entityId → timestamp of last live change (for the violet flash on rows). */
const recent = new Map<Id, number>();
let recentVersion = 0;
const recentListeners = new Set<() => void>();

function setStatus(s: StreamStatus) {
  streamStatus = s;
  statusListeners.forEach((l) => l());
}

export function handleActivity(qc: QueryClient, ev: ActivityEvent) {
  // Prepend to every cached events list (instant feed), then refresh the touched entities.
  qc.setQueriesData<ActivityEvent[] | Page<ActivityEvent>>({ queryKey: qk.events.all }, (old) => {
    if (!old) return old;
    if (Array.isArray(old)) return old.some((e) => e.id === ev.id) ? old : [ev, ...old];
    // A server page: only the unfiltered first page takes the new event live (filtered pages refetch below).
    if (old.offset !== 0 || old.items.some((e) => e.id === ev.id)) return old;
    return { ...old, items: [ev, ...old.items].slice(0, old.limit), total: old.total + 1 };
  });
  qc.invalidateQueries({ queryKey: [...qk.events.all, "page"] });
  (INVALIDATE[ev.entity] ?? []).forEach((k) => qc.invalidateQueries({ queryKey: k }));
  recent.set(ev.entityId, Date.now());
  recentVersion++;
  recentListeners.forEach((l) => l());
  window.setTimeout(() => { recentVersion++; recentListeners.forEach((l) => l()); }, 4100);
  activityListeners.forEach((l) => l(ev));
}

/** Opens the SSE stream once. Mount exactly once (the shell does it). Reconnects with backoff. */
export function useActivityStream() {
  const qc = useQueryClient();
  useEffect(() => {
    let es: EventSource | null = null;
    let retry = 0;
    let timer: number | undefined;
    let closed = false;
    const connect = () => {
      setStatus("connecting");
      es = new EventSource(api.events.streamUrl);
      es.onopen = () => { retry = 0; setStatus("live"); };
      const onMsg = (m: MessageEvent) => {
        try { handleActivity(qc, JSON.parse(m.data) as ActivityEvent); } catch { /* ignore malformed */ }
      };
      es.addEventListener("activity", onMsg as EventListener);
      es.onmessage = onMsg; // tolerate servers that don't name the event
      es.onerror = () => {
        es?.close();
        setStatus("offline");
        if (closed) return;
        timer = window.setTimeout(connect, Math.min(15000, 1000 * 2 ** retry++));
      };
    };
    connect();
    return () => { closed = true; window.clearTimeout(timer); es?.close(); };
  }, [qc]);
}

/** "live" | "connecting" | "offline" — shown in the sidebar footer. */
export function useStreamStatus(): StreamStatus {
  return useSyncExternalStore((l) => { statusListeners.add(l); return () => statusListeners.delete(l); }, () => streamStatus);
}

/** Subscribe to every live ActivityEvent (e.g. the Assistant panel or a page that wants a toast). */
export function useOnActivity(listener: (e: ActivityEvent) => void) {
  useEffect(() => {
    activityListeners.add(listener);
    return () => { activityListeners.delete(listener); };
  }, [listener]);
}

/** True for ~4 s after a live event touched this entity id → add `animate-flash` to the row. */
export function useRecentlyChanged(id?: Id): boolean {
  useSyncExternalStore((l) => { recentListeners.add(l); return () => recentListeners.delete(l); }, () => recentVersion);
  if (!id) return false;
  const t = recent.get(id);
  return !!t && Date.now() - t < 4000;
}
