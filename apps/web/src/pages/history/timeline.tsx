/**
 * Relationship history — shared building blocks (client + supplier events).
 *
 *   <EventTimeline kind="client" events={events} refs={{ orders, invoices }} onResolve={(ev, text) => …} toolbar />
 *
 * - vertical timeline grouped by year → month; each event = type icon + family dot, title, author · channel · date,
 *   expandable description, severity, status (Ouvert / Résolu + resolution), links (order / invoice / PO / products), amount.
 * - `toolbar` adds the built-in filters (families, ouverts, search) — state in the URL (?hf= ?hs= ?hq=).
 *   Pages that filter server-side (the Historique page) pass `toolbar={false}` and pre-filtered events.
 * - paginated with the shared pagination (PAGE_SIZE) when long.
 * Also exported: type labels, families, `NewEventPanel` (SidePanel form), `EventStatsLine`.
 */
import { useMemo, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  AlarmClock, ArrowUpDown, BadgeCheck, BadgePercent, CalendarClock, ChefHat, ChevronDown, CircleCheck, FileText, FileWarning,
  Handshake, History, MapPin, MessageSquareWarning, PackageX, Phone, ReceiptText, Scale, ShieldCheck, Sparkles, StickyNote,
  ThumbsUp, TrendingDown, TrendingUp, TriangleAlert, Truck, Undo2, UserRoundCog, Wallet, type LucideIcon,
} from "lucide-react";
import type { ClientEvent, ClientEventInput, Id, SupplierEvent, SupplierEventInput } from "@kit/shared";
import { cn } from "@/lib/cn";
import { fmtDate, fmtMoney, fmtTime, todayIso } from "@/lib/format";
import { useProducts } from "@/lib/queries";
import { useUrlState } from "@/lib/url-state";
import {
  Button, DatePicker, Dot, EmptyState, Field, Input, Mono, Pagination, SearchInput, Segmented, Select, SidePanel, StatusDot,
  Textarea, usePagination, type Tone,
} from "@/ui";

// ───────────────────────── Types, labels, families ─────────────────────────

export type EventKind = "client" | "supplier";
export type AnyEventType = ClientEvent["type"] | SupplierEvent["type"];
/** A client or supplier event, optionally with the entity name (company-wide lists). */
export type TimelineEvent = (ClientEvent | SupplierEvent) & {
  clientName?: string; supplierName?: string; orderNumber?: string; invoiceNumber?: string; poNumber?: string;
};

export const EVENT_TYPE_LABEL: Record<AnyEventType, string> = {
  onboarding: "Entrée en relation",
  call: "Appel",
  visit: "Visite",
  complaint: "Réclamation",
  quality_issue: "Problème qualité",
  delivery_issue: "Problème de livraison",
  return: "Retour marchandise",
  credit_note: "Avoir",
  dispute: "Litige",
  late_payment: "Incident de paiement",
  payment_plan: "Échéancier",
  price_negotiation: "Négociation tarifaire",
  special_request: "Demande spéciale",
  menu_change: "Changement de carte",
  contact_change: "Changement de contact",
  compliment: "Compliment",
  churn_risk: "Risque de perte",
  won_back: "Client reconquis",
  note: "Note",
  shortage: "Rupture d'approvisionnement",
  price_change: "Changement de prix",
  invoice_issue: "Problème de facture",
  payment: "Paiement",
  contract: "Contrat",
  certification: "Certification",
};

const TYPE_ICON: Record<AnyEventType, LucideIcon> = {
  onboarding: Handshake, call: Phone, visit: MapPin, complaint: MessageSquareWarning, quality_issue: TriangleAlert,
  delivery_issue: Truck, return: Undo2, credit_note: ReceiptText, dispute: Scale, late_payment: AlarmClock,
  payment_plan: CalendarClock, price_negotiation: BadgePercent, special_request: Sparkles, menu_change: ChefHat,
  contact_change: UserRoundCog, compliment: ThumbsUp, churn_risk: TrendingDown, won_back: TrendingUp, note: StickyNote,
  shortage: PackageX, price_change: ArrowUpDown, invoice_issue: FileWarning, payment: Wallet, contract: FileText,
  certification: ShieldCheck,
};

export const CLIENT_EVENT_TYPES: ClientEvent["type"][] = [
  "complaint", "quality_issue", "delivery_issue", "dispute", "churn_risk", "return", "credit_note", "late_payment", "payment_plan",
  "price_negotiation", "special_request", "menu_change", "call", "visit", "onboarding", "contact_change", "compliment", "won_back", "note",
];
export const SUPPLIER_EVENT_TYPES: SupplierEvent["type"][] = [
  "quality_issue", "delivery_issue", "shortage", "dispute", "invoice_issue", "return", "credit_note", "payment",
  "price_change", "price_negotiation", "contract", "certification", "call", "visit", "onboarding", "contact_change", "compliment", "note",
];
/** Types the API opens automatically (they get resolved later). */
export const ISSUE_TYPES = new Set<AnyEventType>([
  "complaint", "quality_issue", "delivery_issue", "return", "dispute", "late_payment", "churn_risk", "shortage", "invoice_issue",
]);

export type FamilyId = "issues" | "returns" | "payments" | "commercial" | "relation" | "notes";
export const FAMILIES: { id: FamilyId; label: string; types: AnyEventType[] }[] = [
  { id: "issues", label: "Réclamations & qualité", types: ["complaint", "quality_issue", "delivery_issue", "dispute", "churn_risk", "shortage", "invoice_issue"] },
  { id: "returns", label: "Retours & avoirs", types: ["return", "credit_note"] },
  { id: "payments", label: "Paiements", types: ["late_payment", "payment_plan", "payment"] },
  { id: "commercial", label: "Commercial", types: ["price_negotiation", "price_change", "special_request", "menu_change", "contract", "certification"] },
  { id: "relation", label: "Relation", types: ["onboarding", "call", "visit", "contact_change", "compliment", "won_back"] },
  { id: "notes", label: "Notes", types: ["note"] },
];
const FAMILY_OF = new Map<AnyEventType, FamilyId>(FAMILIES.flatMap((f) => f.types.map((t) => [t, f.id] as const)));
export const familyOf = (t: AnyEventType): FamilyId => FAMILY_OF.get(t) ?? "notes";
/** Types of the given families that exist for this kind (for the API `type=` filter). */
export function typesOfFamilies(fams: FamilyId[], kind: EventKind): string {
  const valid = new Set<string>(kind === "client" ? CLIENT_EVENT_TYPES : SUPPLIER_EVENT_TYPES);
  return FAMILIES.filter((f) => fams.includes(f.id)).flatMap((f) => f.types).filter((t) => valid.has(t)).join(",");
}

const POSITIVE = new Set<AnyEventType>(["compliment", "won_back", "certification"]);
/** Colour of the event dot: issues red/amber, money amber, relationship violet/blue, positive green. */
export function eventTone(e: Pick<TimelineEvent, "type" | "severity" | "status">): Tone {
  if (POSITIVE.has(e.type)) return "success";
  const fam = familyOf(e.type);
  if (fam === "issues") return e.severity === "low" || e.status === "resolved" ? "warning" : "destructive";
  if (fam === "returns" || fam === "payments") return "warning";
  if (fam === "commercial") return "info";
  if (fam === "relation") return "violet";
  return "muted";
}
const ICON_TONE: Record<Tone, string> = {
  muted: "border-border bg-muted text-muted-foreground",
  info: "border-info/25 bg-info/10 text-info",
  violet: "border-violet/25 bg-violet/10 text-violet",
  success: "border-success/25 bg-success/10 text-success",
  warning: "border-warning/30 bg-warning/10 text-[hsl(32_80%_36%)] dark:text-warning",
  destructive: "border-destructive/25 bg-destructive/10 text-destructive",
  foreground: "border-border bg-muted text-foreground/80",
};

export const CHANNEL_LABEL: Record<NonNullable<ClientEvent["channel"]>, string> = {
  phone: "Téléphone", email: "E-mail", whatsapp: "WhatsApp", visit: "Visite", voice_agent: "Agent vocal", sms: "SMS", other: "Autre",
};
const SEVERITY: Record<NonNullable<ClientEvent["severity"]>, { label: string; tone: Tone }> = {
  low: { label: "Faible", tone: "muted" },
  medium: { label: "Moyenne", tone: "warning" },
  high: { label: "Haute", tone: "destructive" },
};

const MONTH = new Intl.DateTimeFormat("fr-FR", { month: "long" });
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

// ───────────────────────── Filters ─────────────────────────

/** URL-backed filter state of the built-in toolbar. */
export function useTimelineFilters() {
  const [fam, setFam] = useUrlState("hf");
  const [status, setStatus] = useUrlState("hs");
  const [q, setQ] = useUrlState("hq");
  const families = useMemo(() => (fam ? (fam.split(",") as FamilyId[]) : []), [fam]);
  const toggleFamily = (f: FamilyId) =>
    setFam((families.includes(f) ? families.filter((x) => x !== f) : [...families, f]).join(","));
  return { families, setFamilies: (f: FamilyId[]) => setFam(f.join(",")), toggleFamily, status, setStatus, q, setQ };
}

const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
export function filterTimeline(events: TimelineEvent[], f: { families: FamilyId[]; status: string; q: string }) {
  const tokens = norm(f.q).split(/\s+/).filter(Boolean);
  return events.filter((e) => {
    if (f.families.length && !f.families.includes(familyOf(e.type))) return false;
    if (f.status && e.status !== f.status) return false;
    if (tokens.length) {
      const text = norm(`${e.title} ${e.description} ${e.author} ${e.resolution ?? ""} ${EVENT_TYPE_LABEL[e.type]}`);
      if (!tokens.every((t) => text.includes(t))) return false;
    }
    return true;
  });
}

/** Family chips (multi-select). */
export function FamilyChips({ value, onToggle, onClear, counts }: {
  value: FamilyId[]; onToggle: (f: FamilyId) => void; onClear: () => void; counts?: Partial<Record<FamilyId, number>>;
}) {
  const chip = (on: boolean) =>
    cn(
      "inline-flex h-[26px] items-center gap-1.5 whitespace-nowrap rounded-[4px] border px-2 text-[12.5px] transition-colors",
      on ? "border-foreground/30 bg-muted font-medium text-foreground" : "border-border text-muted-foreground hover:border-border-hover hover:text-foreground",
    );
  return (
    <div className="flex flex-wrap items-center gap-1">
      <button type="button" className={chip(value.length === 0)} onClick={onClear}>Tout</button>
      {FAMILIES.map((f) => {
        const n = counts?.[f.id];
        if (counts && !n && !value.includes(f.id)) return null;
        const on = value.includes(f.id);
        return (
          <button key={f.id} type="button" aria-pressed={on} className={chip(on)} onClick={() => onToggle(f.id)}>
            <Dot tone={eventTone({ type: f.types[0], severity: "high" })} />
            {f.label}
            {n !== undefined ? <span className="num text-[11.5px] text-muted-foreground">{n}</span> : null}
          </button>
        );
      })}
    </div>
  );
}

// ───────────────────────── Timeline ─────────────────────────

/** productId → name (cached catalogue), for the product links of events. */
export function useProductNames() {
  const { data: products } = useProducts();
  return useMemo(() => new Map((products ?? []).map((p) => [p.id, p.name])), [products]);
}

/** Slim row under a detail page header: the entity's groups (tags) with inline add/remove. */
export function GroupsStrip({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-9 flex-wrap items-center gap-2 border-b border-border px-5 py-1.5">
      <span className="text-[10.5px] font-semibold uppercase tracking-[.08em] text-muted-foreground">Groupes</span>
      {children}
    </div>
  );
}

export interface TimelineRefs {
  orders?: Map<Id, string>;
  invoices?: Map<Id, string>;
  purchaseOrders?: Map<Id, string>;
}

export function EventTimeline({
  kind, events, total, loading, refs, onResolve, resolvingId, toolbar = true, showEntity, pageKey = "histPage", empty, className,
}: {
  kind: EventKind;
  /** Client-side: every event (filtered and paged here). Server-side (`total` set): the current page only. */
  events: TimelineEvent[] | undefined;
  /** Server-side pagination: number of events matching the (server) filters; `pageKey` is the page param of the query. */
  total?: number;
  loading?: boolean;
  refs?: TimelineRefs;
  /** Inline "Marquer résolu" on open events. */
  onResolve?: (ev: TimelineEvent, resolution: string) => void;
  resolvingId?: Id;
  /** Built-in filter bar (families, ouverts, search). */
  toolbar?: boolean;
  /** Show the client / supplier name with a link (company-wide lists). */
  showEntity?: boolean;
  pageKey?: string;
  empty?: ReactNode;
  className?: string;
}) {
  const f = useTimelineFilters();
  const all = events ?? [];
  const filtered = useMemo(() => (toolbar ? filterTimeline(all, f) : all), [all, toolbar, f.families, f.status, f.q]); // eslint-disable-line react-hooks/exhaustive-deps
  const famCounts = useMemo(() => {
    const c: Partial<Record<FamilyId, number>> = {};
    for (const e of all) c[familyOf(e.type)] = (c[familyOf(e.type)] ?? 0) + 1;
    return c;
  }, [all]);
  const server = total !== undefined || (!toolbar && events === undefined);
  const pg = usePagination(server ? events : filtered, server ? { key: pageKey, server: true, total } : { key: pageKey });
  const productName = useProductNames();

  const groups = useMemo(() => groupByMonth(pg.rows), [pg.rows]);
  const yearTotals = useMemo(() => {
    const m = new Map<string, number>();
    for (const e of filtered) m.set(e.at.slice(0, 4), (m.get(e.at.slice(0, 4)) ?? 0) + 1);
    return m;
  }, [filtered]);
  const openCount = all.filter((e) => e.status === "open").length;

  return (
    <div className={cn("flex min-w-0 flex-col", className)}>
      {toolbar ? (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <FamilyChips value={f.families} onToggle={f.toggleFamily} onClear={() => f.setFamilies([])} counts={famCounts} />
          <div className="ml-auto flex items-center gap-2">
            <Segmented
              value={(f.status || "all") as "all" | "open" | "resolved"}
              onChange={(v) => f.setStatus(v === "all" ? "" : v)}
              options={[{ id: "all", label: "Tous" }, { id: "open", label: `Ouverts${openCount ? ` · ${openCount}` : ""}` }, { id: "resolved", label: "Résolus" }]}
            />
            <SearchInput value={f.q} onChange={f.setQ} placeholder="Rechercher dans l'historique…" className="w-56" />
          </div>
        </div>
      ) : null}

      <div ref={pg.anchorRef} />
      {loading && !events ? (
        <TimelineSkeleton />
      ) : filtered.length === 0 ? (
        empty ?? (
          <EmptyState
            compact
            icon={History}
            title={all.length ? "Aucun événement ne correspond" : "Aucun historique"}
            description={all.length ? "Modifiez les filtres ou la recherche." : "Les appels, réclamations, retours et négociations apparaîtront ici."}
          />
        )
      ) : (
        <div className="flex flex-col">
          {groups.map((y) => (
            <section key={y.year} className="flex flex-col">
              <div className="sticky top-0 z-[1] -mx-1 flex items-baseline gap-2 bg-background/95 px-1 py-1.5 backdrop-blur">
                <span className="num text-[13px] font-semibold">{y.year}</span>
                <span className="num text-[11.5px] text-muted-foreground">{yearTotals.get(y.year) ?? y.count} événement{(yearTotals.get(y.year) ?? y.count) > 1 ? "s" : ""}</span>
                <span className="ml-2 h-px flex-1 bg-border" />
              </div>
              {y.months.map((m) => (
                <div key={m.key} className="flex flex-col">
                  <div className="pb-1 pl-[34px] pt-2 text-[10.5px] font-semibold uppercase tracking-[.08em] text-muted-foreground">
                    {m.label}
                  </div>
                  <ol className="relative flex flex-col">
                    <span aria-hidden className="absolute bottom-3 left-[11px] top-3 w-px bg-border" />
                    {m.events.map((e) => (
                      <EventItem
                        key={e.id}
                        kind={kind}
                        ev={e}
                        refs={refs}
                        productName={productName}
                        showEntity={showEntity}
                        onResolve={onResolve}
                        resolving={resolvingId === e.id}
                      />
                    ))}
                  </ol>
                </div>
              ))}
            </section>
          ))}
        </div>
      )}
      <Pagination pagination={pg} className="mt-2 px-0">
        {pg.total} événement{pg.total > 1 ? "s" : ""}
      </Pagination>
    </div>
  );
}

function groupByMonth(events: TimelineEvent[]) {
  const years: { year: string; count: number; months: { key: string; label: string; events: TimelineEvent[] }[] }[] = [];
  for (const e of events) {
    const year = e.at.slice(0, 4);
    const key = e.at.slice(0, 7);
    let y = years[years.length - 1];
    if (!y || y.year !== year) years.push((y = { year, count: 0, months: [] }));
    let m = y.months[y.months.length - 1];
    if (!m || m.key !== key) {
      const d = new Date(Number(year), Number(key.slice(5, 7)) - 1, 1);
      y.months.push((m = { key, label: cap(MONTH.format(d)), events: [] }));
    }
    m.events.push(e);
    y.count++;
  }
  return years;
}

/** One event. Also used standalone for the "open issues" block (highlight). */
export function EventItem({
  kind, ev, refs, productName, showEntity, onResolve, resolving, highlight,
}: {
  kind: EventKind;
  ev: TimelineEvent;
  refs?: TimelineRefs;
  productName?: Map<Id, string>;
  showEntity?: boolean;
  onResolve?: (ev: TimelineEvent, resolution: string) => void;
  resolving?: boolean;
  highlight?: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const [resolveOpen, setResolveOpen] = useState(false);
  const [resolution, setResolution] = useState("");
  const tone = eventTone(ev);
  const Icon = TYPE_ICON[ev.type] ?? StickyNote;
  const long = ev.description.length > 180;
  const links = eventLinks(kind, ev, refs, productName);
  const entity = showEntity ? entityOf(ev) : undefined;
  const submit = () => { onResolve?.(ev, resolution.trim()); };

  return (
    <li className={cn("group relative flex gap-3 py-2", highlight && "rounded-[6px] border border-warning/40 bg-warning/[.06] px-3")}>
      <span
        className={cn(
          "relative z-[1] mt-[1px] flex h-[23px] w-[23px] shrink-0 items-center justify-center rounded-full border",
          ICON_TONE[tone],
          !highlight && "ring-4 ring-background",
        )}
        title={EVENT_TYPE_LABEL[ev.type]}
      >
        <Icon size={12} strokeWidth={1.9} />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex min-w-0 items-start gap-3">
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 flex-wrap items-center gap-x-2 gap-y-0.5">
              {entity ? (
                <Link to={entity.to} className="truncate font-medium text-foreground hover:underline">{entity.name}</Link>
              ) : null}
              {entity ? <span className="text-muted-foreground/60">·</span> : null}
              <span className={cn("min-w-0 text-[13px] leading-[19px]", entity ? "text-secondary-foreground" : "font-medium")}>{ev.title}</span>
            </div>
            <div className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-[11.5px] text-muted-foreground">
              <span className="text-secondary-foreground/80">{EVENT_TYPE_LABEL[ev.type]}</span>
              <span>·</span>
              <span>{ev.author}</span>
              {ev.channel ? <><span>·</span><span>{CHANNEL_LABEL[ev.channel] ?? ev.channel}</span></> : null}
              <span>·</span>
              <span className="num" title={ev.at}>{fmtDate(ev.at)} {new Date(ev.at).getFullYear()} · {fmtTime(ev.at)}</span>
              {ev.severity ? (
                <><span>·</span><span className="inline-flex items-center gap-1"><Dot tone={SEVERITY[ev.severity].tone} />Gravité {SEVERITY[ev.severity].label.toLowerCase()}</span></>
              ) : null}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-3 pt-[1px]">
            {ev.amount ? <span className="num text-[12.5px] font-medium">{fmtMoney(ev.amount)}</span> : null}
            {ev.status === "open" ? <StatusDot tone="warning" label="Ouvert" /> : ev.status === "resolved" ? <StatusDot tone="success" label="Résolu" /> : null}
          </div>
        </div>

        {ev.description ? (
          <div className="mt-1 max-w-[860px] text-[12.5px] leading-[18px] text-secondary-foreground">
            <p className={cn("whitespace-pre-wrap", !expanded && long && "line-clamp-2")}>{ev.description}</p>
            {long ? (
              <button type="button" onClick={() => setExpanded((x) => !x)} className="mt-0.5 inline-flex items-center gap-0.5 text-[11.5px] text-muted-foreground hover:text-foreground">
                {expanded ? "Réduire" : "Lire la suite"}
                <ChevronDown size={12} className={cn("transition-transform", expanded && "rotate-180")} />
              </button>
            ) : null}
          </div>
        ) : null}

        {links.length ? (
          <div className="mt-1.5 flex flex-wrap items-center gap-1">
            {links.map((l) => (
              <Link key={l.key} to={l.to} className="inline-flex h-5 items-center gap-1 rounded-[3px] border border-border bg-card px-1.5 text-[11.5px] text-secondary-foreground hover:border-border-hover hover:text-foreground">
                <span className="text-muted-foreground">{l.kind}</span>
                {l.mono ? <Mono className="text-[11px]">{l.label}</Mono> : <span>{l.label}</span>}
              </Link>
            ))}
          </div>
        ) : null}

        {ev.status === "resolved" && (ev.resolution || ev.resolvedAt) ? (
          <div className="mt-1.5 flex max-w-[860px] items-start gap-1.5 text-[12px] text-muted-foreground">
            <CircleCheck size={13} strokeWidth={1.75} className="mt-[2px] shrink-0 text-success" />
            <span>
              {ev.resolvedAt ? <span className="text-secondary-foreground">Résolu le {fmtDate(ev.resolvedAt)} {new Date(ev.resolvedAt).getFullYear()}</span> : "Résolu"}
              {ev.resolution ? <> — {ev.resolution}</> : null}
            </span>
          </div>
        ) : null}

        {ev.status === "open" && onResolve ? (
          resolveOpen ? (
            <div className="mt-2 flex max-w-[720px] items-center gap-2">
              <Input
                size="sm"
                autoFocus
                value={resolution}
                onChange={(e) => setResolution(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submit();
                  if (e.key === "Escape") { e.preventDefault(); setResolveOpen(false); }
                }}
                placeholder="Comment c'est réglé ? (ex. avoir de 84 € accordé, lot remplacé)"
                className="flex-1"
                aria-label="Résolution"
              />
              <Button size="sm" variant="ghost" onClick={() => setResolveOpen(false)}>Annuler</Button>
              <Button size="sm" variant="primary" icon={BadgeCheck} loading={resolving} onClick={submit}>Résoudre</Button>
            </div>
          ) : (
            <Button size="sm" variant={highlight ? "default" : "ghost"} icon={BadgeCheck} className={cn("mt-1.5", !highlight && "-ml-2")} onClick={() => setResolveOpen(true)}>
              Marquer résolu
            </Button>
          )
        ) : null}
      </div>
    </li>
  );
}

function entityOf(ev: TimelineEvent): { name: string; to: string } | undefined {
  if ("clientId" in ev) return { name: ev.clientName ?? ev.clientId, to: `/clients/${ev.clientId}?tab=history` };
  if ("supplierId" in ev) return { name: ev.supplierName ?? ev.supplierId, to: `/suppliers/${ev.supplierId}?tab=history` };
  return undefined;
}

function eventLinks(kind: EventKind, ev: TimelineEvent, refs?: TimelineRefs, productName?: Map<Id, string>) {
  const out: { key: string; kind: string; label: string; to: string; mono?: boolean }[] = [];
  if ("orderId" in ev && ev.orderId) out.push({ key: "o", kind: "Commande", label: ev.orderNumber ?? refs?.orders?.get(ev.orderId) ?? ev.orderId, to: `/orders/${ev.orderId}`, mono: true });
  if ("invoiceId" in ev && ev.invoiceId) out.push({ key: "i", kind: "Facture", label: ev.invoiceNumber ?? refs?.invoices?.get(ev.invoiceId) ?? ev.invoiceId, to: `/invoices/${ev.invoiceId}`, mono: true });
  if ("purchaseOrderId" in ev && ev.purchaseOrderId)
    out.push({ key: "po", kind: "Achat", label: ev.poNumber ?? refs?.purchaseOrders?.get(ev.purchaseOrderId) ?? ev.purchaseOrderId, to: `/purchase-orders/${ev.purchaseOrderId}`, mono: true });
  const pids = ev.productIds ?? [];
  for (const pid of pids.slice(0, 4)) out.push({ key: `p${pid}`, kind: "", label: productName?.get(pid) ?? pid, to: `/products/${pid}` });
  if (pids.length > 4) out.push({ key: "more", kind: "", label: `+${pids.length - 4} produits`, to: `/products/${pids[4]}` });
  void kind;
  return out;
}

function TimelineSkeleton() {
  return (
    <div className="flex flex-col gap-4 py-2">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="flex gap-3">
          <span className="h-[23px] w-[23px] shrink-0 animate-pulse rounded-full bg-muted" />
          <div className="flex flex-1 flex-col gap-1.5">
            <span className="h-3 w-2/5 animate-pulse rounded-[3px] bg-muted" />
            <span className="h-2.5 w-1/4 animate-pulse rounded-[3px] bg-muted" />
            <span className="h-2.5 w-3/4 animate-pulse rounded-[3px] bg-muted" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ───────────────────────── Stats line ─────────────────────────

/** "Client depuis 2016 · 85 événements · 2 ouverts · 2 réclamations sur 12 mois" */
export function EventStatsLine({ kind, stats, className }: {
  kind: EventKind;
  stats: { total: number; open: number; since?: string; complaints12m?: number; returns12m?: number; issues12m?: number };
  className?: string;
}) {
  const parts: ReactNode[] = [];
  if (stats.since) parts.push(<>{kind === "client" ? "Client" : "Fournisseur"} depuis <b className="num font-medium text-foreground">{stats.since.slice(0, 4)}</b></>);
  parts.push(<><b className="num font-medium text-foreground">{stats.total}</b> événement{stats.total > 1 ? "s" : ""}</>);
  parts.push(
    <span className={stats.open ? "text-[hsl(32_80%_36%)] dark:text-warning" : undefined}>
      <b className="num font-medium">{stats.open}</b> ouvert{stats.open > 1 ? "s" : ""}
    </span>,
  );
  if (stats.complaints12m !== undefined)
    parts.push(<><b className="num font-medium text-foreground">{stats.complaints12m}</b> réclamation{stats.complaints12m > 1 ? "s" : ""} sur 12 mois</>);
  if (stats.returns12m) parts.push(<><b className="num font-medium text-foreground">{stats.returns12m}</b> retour{stats.returns12m > 1 ? "s" : ""} sur 12 mois</>);
  if (stats.issues12m !== undefined)
    parts.push(<><b className="num font-medium text-foreground">{stats.issues12m}</b> incident{stats.issues12m > 1 ? "s" : ""} sur 12 mois</>);
  return (
    <div className={cn("flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[12.5px] text-muted-foreground", className)}>
      {parts.map((p, i) => (
        <span key={i} className="inline-flex items-center gap-2">{i > 0 ? <span className="text-muted-foreground/50">·</span> : null}<span>{p}</span></span>
      ))}
    </div>
  );
}

// ───────────────────────── New event (side panel) ─────────────────────────

export type NewEventBody = (ClientEventInput | SupplierEventInput) & Record<string, unknown>;

export function NewEventPanel({ kind, subtitle, onClose, onSubmit, pending, links }: {
  kind: EventKind;
  subtitle?: string;
  onClose: () => void;
  onSubmit: (body: NewEventBody) => void;
  pending?: boolean;
  /** Link pickers: client → orders + invoices; supplier → purchase orders. */
  links: { field: "orderId" | "invoiceId" | "purchaseOrderId"; label: string; options: { value: string; label: string }[] }[];
}) {
  const types = kind === "client" ? CLIENT_EVENT_TYPES : SUPPLIER_EVENT_TYPES;
  const [type, setType] = useState<AnyEventType>(types[0]);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [channel, setChannel] = useState<string>("phone");
  const [severity, setSeverity] = useState<"" | "low" | "medium" | "high">("medium");
  const [date, setDate] = useState(todayIso());
  const [author, setAuthor] = useState("");
  const [amount, setAmount] = useState("");
  const [linkVals, setLinkVals] = useState<Record<string, string>>({});
  const issue = ISSUE_TYPES.has(type);

  const typeOptions = FAMILIES.flatMap((f) =>
    f.types.filter((t) => (types as string[]).includes(t)).map((t) => ({ value: t, label: `${f.label} — ${EVENT_TYPE_LABEL[t]}` })),
  );
  const submit = () => {
    if (!title.trim()) return;
    const body: NewEventBody = {
      type: type as never,
      title: title.trim(),
      ...(description.trim() ? { description: description.trim() } : {}),
      ...(channel ? { channel: channel as never } : {}),
      ...(severity ? { severity } : {}),
      ...(date && date !== todayIso() ? { at: date } : {}),
      ...(author.trim() ? { author: author.trim() } : {}),
      ...(amount && !Number.isNaN(Number(amount.replace(",", "."))) ? { amount: Number(amount.replace(",", ".")) } : {}),
      ...Object.fromEntries(Object.entries(linkVals).filter(([, v]) => v)),
    };
    onSubmit(body);
  };

  return (
    <SidePanel
      id="new-event"
      title="Nouvel événement"
      subtitle={subtitle}
      onClose={onClose}
      footer={
        <>
          <span className="mr-auto text-[11.5px] text-muted-foreground">{issue ? "Sera créé « Ouvert »" : "⌘↵ pour enregistrer"}</span>
          <Button variant="ghost" onClick={onClose}>Annuler</Button>
          <Button variant="primary" loading={pending} disabled={!title.trim()} onClick={submit} kbd="⌘↵">Enregistrer</Button>
        </>
      }
    >
      <div
        className="flex flex-col gap-3.5"
        onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit(); }}
      >
        <Field label="Type">
          <Select value={type} onChange={(v) => setType(v as AnyEventType)} options={typeOptions} className="w-full" />
        </Field>
        <Field label="Titre">
          <Input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder={kind === "client" ? "Ex. : langoustines arrivées mortes" : "Ex. : camion arrivé à 7 h au lieu de 4 h"} />
        </Field>
        <Field label="Description">
          <Textarea rows={4} value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Ce qui s'est passé, avec les mots du client si possible." />
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date">
            <DatePicker value={date} onChange={(v) => setDate(v || todayIso())} max={todayIso()} presets={[{ label: "Aujourd'hui", days: 0 }, { label: "Hier", days: -1 }, { label: "−7 j", days: -7 }]} />
          </Field>
          <Field label="Canal">
            <Select className="w-full" value={channel} onChange={setChannel} placeholder="—" options={Object.entries(CHANNEL_LABEL).map(([value, label]) => ({ value, label }))} />
          </Field>
        </div>
        <Field label="Gravité">
          <Segmented
            value={(severity || "none") as "none" | "low" | "medium" | "high"}
            onChange={(v) => setSeverity(v === "none" ? "" : v)}
            options={[{ id: "none", label: "—" }, { id: "low", label: "Faible" }, { id: "medium", label: "Moyenne" }, { id: "high", label: "Haute" }]}
          />
        </Field>
        {links.map((l) => (
          <Field key={l.field} label={l.label}>
            <Select className="w-full" value={linkVals[l.field] ?? ""} onChange={(v) => setLinkVals((x) => ({ ...x, [l.field]: v }))} placeholder="Aucun lien" options={l.options} />
          </Field>
        ))}
        <div className="grid grid-cols-2 gap-3">
          <Field label="Montant (€)" hint="Avoir, litige, dette…">
            <Input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0,00" />
          </Field>
          <Field label="Auteur">
            <Input value={author} onChange={(e) => setAuthor(e.target.value)} placeholder="Équipe" />
          </Field>
        </div>
      </div>
    </SidePanel>
  );
}
