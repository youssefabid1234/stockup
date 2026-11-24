/**
 * Team 12 (Youssef) · « Aujourd'hui » : the wholesaler's home (StockUp), only what matters today, all actionable in place.
 *   key figures first (click = jump / filter) · who contacted us today · orders in progress (quote → confirmed →
 *   prepared → delivered) · what to collect, with « Virement reçu » · stock-outs in red. The rest: « Historique et détails ».
 */
import { useMemo, useRef, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowRight, Bot, Check, ClipboardList, Euro, History, PackageX, Phone, PhoneCall, ShoppingCart, Truck, Wallet, X,
} from "lucide-react";
import type { InvoiceSummary, OrderSummary } from "@kit/shared";
import { StockUpLogo } from "@/app/StockUpLogo";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fmtDateLong } from "@/lib/format";
import { Money, Page, PageBody } from "@/ui";

const LIVE = { refetchInterval: 5000 };
type Filter = "all" | "draft" | "soon";
const STEP: Record<string, { label: string; run: (id: string) => Promise<unknown> } | undefined> = {
  draft: { label: "Confirmer", run: api.orders.confirm },
  confirmed: { label: "Préparée", run: (id) => api.orders.prepare(id) },
  prepared: { label: "Livrée", run: api.orders.deliver },
};
const STATUS: Record<string, { label: string; color: string }> = {
  draft: { label: "Devis", color: "#D97706" },
  confirmed: { label: "Confirmée", color: "#1F6BFF" },
  prepared: { label: "Préparée", color: "#7C3AED" },
};
const pill = (color: string) => ({ background: `${color}1f`, color });
const PALETTE = ["#1F6BFF", "#7C3AED", "#0EA5E9", "#F59E0B", "#10B981", "#EC4899", "#6366F1", "#14B8A6"];
const items = <T,>(d: unknown): T[] => (Array.isArray(d) ? d : ((d as { items?: T[] })?.items ?? []));
const initials = (name: string) => name.replace(/^(La|Le|Les|Au|Aux|L')\s+/i, "").split(/[\s'-]+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join("");
const colorOf = (id: string) => PALETTE[[...id].reduce((s, c) => s + c.charCodeAt(0), 0) % PALETTE.length];

function Avatar({ id, name }: { id: string; name: string }) {
  return <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[11.5px] font-bold text-white shadow-sm" style={{ background: colorOf(id) }}>{initials(name)}</span>;
}

export default function TodayPage() {
  const navigate = useNavigate();
  const dash = useQuery({ queryKey: ["today", "dashboard"], queryFn: api.dashboard, ...LIVE });
  const d = dash.data;
  const today = d?.today;
  const [filter, setFilter] = useState<Filter>("all");
  const collectRef = useRef<HTMLDivElement>(null);
  const stockRef = useRef<HTMLDivElement>(null);
  const ordersRef = useRef<HTMLDivElement>(null);
  const go = (ref: React.RefObject<HTMLDivElement | null>) => ref.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  const outs = d?.lowStock.filter((s) => s.available <= 0).length ?? 0;
  const hourNow = new Date().getHours();

  return (
    <Page>
      <PageBody flush>
        <div className="min-h-full bg-gradient-to-b from-[#1F6BFF]/[.07] via-transparent to-transparent">
          {/* Hero */}
          <header className="flex flex-wrap items-center gap-4 px-6 pb-5 pt-12">
            <StockUpLogo size={34} />
            <div className="ml-2 border-l border-border pl-5">
              <h1 className="text-[22px] font-bold tracking-tight text-[#0F1E45] dark:text-white">
                {hourNow < 18 ? "Bonjour" : "Bonsoir"}, voici votre journée
              </h1>
              <p className="flex items-center gap-2 text-[13px] capitalize text-muted-foreground">
                {today ? fmtDateLong(today) : "…"}
                <span className="flex items-center gap-1 normal-case"><span className="h-2 w-2 animate-pulse rounded-full bg-emerald-500" /> en direct</span>
              </p>
            </div>
            <div className="ml-auto flex gap-2">
              <button onClick={() => navigate("/voice")}
                className="flex items-center gap-2 rounded-full bg-[#1F6BFF] px-4 py-2.5 text-[13.5px] font-semibold text-white shadow-md shadow-[#1F6BFF]/25 transition hover:-translate-y-0.5 hover:bg-[#1857d6]">
                <PhoneCall size={16} /> Standard · Lucie
              </button>
              <button onClick={() => navigate("/dashboard")}
                className="flex items-center gap-2 rounded-full border border-border bg-card px-4 py-2.5 text-[13.5px] font-medium shadow-sm transition hover:-translate-y-0.5 hover:border-[#1F6BFF]/40 hover:text-[#1F6BFF]">
                <History size={16} /> Historique et détails
              </button>
            </div>
          </header>

          {/* Key figures */}
          <div className="grid grid-cols-2 gap-3 px-6 md:grid-cols-3 xl:grid-cols-5">
            <Kpi icon={Euro} tone="#1F6BFF" label="Chiffre du jour" value={d ? <Money value={d.revenueToday} /> : "…"} hint="voir le détail" onClick={() => navigate("/dashboard")} />
            <Kpi icon={Truck} tone="#7C3AED" label="À livrer aujourd'hui" value={d?.toDeliverToday ?? "…"} hint="commandes à livrer" onClick={() => { setFilter("soon"); go(ordersRef); }} />
            <Kpi icon={ClipboardList} tone="#F59E0B" label="Devis à valider" value={d?.draftOrders ?? "…"} hint="à confirmer" onClick={() => { setFilter("draft"); go(ordersRef); }} />
            <Kpi icon={Wallet} tone="#EF4444" label="Impayés en retard" value={d ? <Money value={d.overdueInvoicesAmount} /> : "…"} hint={d ? `${d.overdueInvoicesCount} factures` : ""} alert onClick={() => go(collectRef)} />
            <Kpi icon={PackageX} tone="#E11D48" label="Ruptures" value={outs} hint={`${d?.lowStock.length ?? 0} produits à surveiller`} alert={outs > 0} onClick={() => go(stockRef)} />
          </div>

          <div className="grid grid-cols-1 gap-4 p-6 lg:grid-cols-[1fr_1.35fr_1.2fr]">
            <Contacts today={today} />
            <div ref={ordersRef} className="min-w-0 scroll-mt-4"><Orders today={today} filter={filter} setFilter={setFilter} /></div>
            <div className="flex min-w-0 flex-col gap-4">
              <div ref={collectRef} className="scroll-mt-4"><ToCollect /></div>
              <div ref={stockRef} className="scroll-mt-4"><StockOuts low={d?.lowStock ?? []} /></div>
            </div>
          </div>
        </div>
      </PageBody>
    </Page>
  );
}

function Kpi({ icon: Icon, tone, label, value, hint, alert, onClick }: {
  icon: typeof Euro; tone: string; label: string; value: ReactNode; hint?: string; alert?: boolean; onClick: () => void;
}) {
  return (
    <button onClick={onClick}
      className="group relative overflow-hidden rounded-2xl border border-border bg-card p-4 text-left shadow-sm transition hover:-translate-y-1 hover:shadow-lg"
      style={{ boxShadow: alert ? `inset 0 3px 0 ${tone}` : undefined }}>
      <span className="absolute -right-6 -top-6 h-24 w-24 rounded-full opacity-[.08] transition group-hover:scale-125" style={{ background: tone }} />
      <span className="flex h-10 w-10 items-center justify-center rounded-xl text-white shadow-sm" style={{ background: tone }}><Icon size={19} /></span>
      <div className="mt-3 text-[12px] font-medium uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-0.5 text-[26px] font-bold leading-8 tabular-nums" style={{ color: alert ? tone : undefined }}>{value}</div>
      <div className="mt-1 flex items-center gap-1 text-[12px] text-muted-foreground transition group-hover:text-foreground">{hint} <ArrowRight size={12} className="opacity-0 transition group-hover:translate-x-0.5 group-hover:opacity-100" /></div>
    </button>
  );
}

function Card({ title, icon: Icon, tone, count, alert, children, extra }: {
  title: string; icon: typeof Phone; tone: string; count?: number; alert?: boolean; children: ReactNode; extra?: ReactNode;
}) {
  return (
    <section className="flex min-h-0 min-w-0 flex-col overflow-hidden rounded-2xl border border-border bg-card shadow-sm">
      <h2 className="flex items-center gap-2.5 px-4 pb-2 pt-3.5 text-[14px] font-semibold">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg" style={{ background: `${tone}1a`, color: tone }}><Icon size={15} /></span>
        {title}
        {count != null ? (
          <span className="ml-auto rounded-full px-2.5 py-0.5 text-[12px] font-semibold" style={alert ? { background: `${tone}1a`, color: tone } : undefined}>
            <span className={alert ? "" : "text-muted-foreground"}>{count}</span>
          </span>
        ) : null}
      </h2>
      {extra}
      <div className="max-h-[calc(100vh-330px)] min-h-[120px] overflow-y-auto pb-2">{children}</div>
    </section>
  );
}

function Contacts({ today }: { today?: string }) {
  const events = useQuery({ queryKey: ["today", "events"], queryFn: () => api.events.list({ limit: 300 }), ...LIVE });
  const clients = useQuery({ queryKey: ["today", "clients"], queryFn: () => api.clients.list(), staleTime: 60_000 });
  const rows = useMemo(() => {
    const byClient = new Map<string, { id: string; name: string; last: string; at: string; n: number; ai: boolean }>();
    for (const e of items<{ entity: string; entityId: string; at: string; summary: string; actor: string }>(events.data)) {
      if (e.entity !== "client" || !today || !e.at.startsWith(today)) continue;
      const name = clients.data?.find((c) => c.id === e.entityId)?.name ?? e.summary.match(/pour (.+?) :/)?.[1] ?? e.entityId;
      const row = byClient.get(e.entityId);
      if (row) row.n++;
      else byClient.set(e.entityId, { id: e.entityId, name, last: e.summary.replace(/^.*?: /, "").replace(/^« |»$/g, ""), at: e.at, n: 1, ai: e.actor === "voice_agent" });
    }
    return [...byClient.values()];
  }, [events.data, today, clients.data]);
  return (
    <Card title="Qui nous a contacté aujourd'hui" icon={Phone} tone="#10B981" count={rows.length}>
      {rows.length === 0 ? <p className="px-4 py-6 text-center text-[13px] text-muted-foreground">{events.isPending ? "Chargement…" : "Personne pour l'instant."}</p> : null}
      <ul className="space-y-0.5 px-2">
        {rows.map((r) => (
          <li key={r.id}>
            <Link to={`/clients/${r.id}`} className="group flex items-center gap-3 rounded-xl px-2 py-2 transition hover:bg-muted">
              <Avatar id={r.id} name={r.name} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px] font-semibold">{r.name}</span>
                <span className="flex items-center gap-1 truncate text-[12px] text-muted-foreground">
                  {r.ai ? <Bot size={12} className="shrink-0 text-[#1F6BFF]" /> : null}<span className="truncate">{r.last}</span>
                </span>
              </span>
              <span className="shrink-0 text-right text-[11.5px] text-muted-foreground">
                {r.at.slice(11, 16)}{r.n > 1 ? <span className="block">{r.n} échanges</span> : null}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Orders({ today, filter, setFilter }: { today?: string; filter: Filter; setFilter: (f: Filter) => void }) {
  const qc = useQueryClient();
  const orders = useQuery({
    queryKey: ["today", "orders"],
    queryFn: async () => (await Promise.all(["draft", "confirmed", "prepared"].map((status) => api.orders.list({ status, limit: 200 } as never)))).flat(),
    ...LIVE,
  });
  const [moved, setMoved] = useState<string>();
  const step = useMutation({
    mutationFn: ({ o }: { o: OrderSummary }) => STEP[o.status]!.run(o.id),
    onSuccess: (_r, { o }) => setMoved(`${o.clientName} : ${STEP[o.status]!.label.toLowerCase()}`),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["today"] }),
  });
  const tomorrow = today ? new Date(Date.parse(today) + 86400000).toISOString().slice(0, 10) : "";
  const all = (orders.data ?? []) as OrderSummary[];
  const shown = all
    .filter((o) => filter === "all" || (filter === "draft" ? o.status === "draft" : o.deliveryDate <= tomorrow))
    .sort((a, b) => a.deliveryDate.localeCompare(b.deliveryDate))
    .slice(0, 80);
  const tab = (key: Filter, label: string, n: number) => (
    <button onClick={() => setFilter(key)}
      className={cn("rounded-full px-3 py-1 text-[12px] font-medium transition", filter === key ? "bg-[#0F1E45] text-white shadow-sm dark:bg-white dark:text-[#0F1E45]" : "bg-muted text-muted-foreground hover:text-foreground")}>
      {label} <span className="opacity-70">{n}</span>
    </button>
  );
  return (
    <Card title="Commandes en cours" icon={ShoppingCart} tone="#1F6BFF" count={all.length}
      extra={
        <div className="flex flex-wrap gap-1.5 px-4 pb-2">
          {tab("all", "Toutes", all.length)}
          {tab("soon", "Aujourd'hui / demain", all.filter((o) => o.deliveryDate <= tomorrow).length)}
          {tab("draft", "Devis", all.filter((o) => o.status === "draft").length)}
          {moved ? <span className="ml-auto flex items-center gap-1 text-[12px] text-emerald-600"><Check size={13} /> {moved}</span> : null}
        </div>
      }>
      <ul className="space-y-0.5 px-2">
        {shown.map((o) => {
          const next = STEP[o.status];
          const when = o.deliveryDate === today ? "aujourd'hui" : o.deliveryDate === tomorrow ? "demain" : `${o.deliveryDate.slice(8, 10)}/${o.deliveryDate.slice(5, 7)}`;
          return (
            <li key={o.id} className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 text-[13px] transition hover:bg-muted">
              <Avatar id={o.clientId} name={o.clientName ?? "?"} />
              <Link to={`/orders/${o.id}`} className="min-w-0 flex-1">
                <span className="flex items-baseline gap-2">
                  <span className="min-w-0 flex-1 truncate font-semibold hover:text-[#1F6BFF]">{o.clientName}</span>
                  <span className="shrink-0 font-semibold tabular-nums"><Money value={o.totalHt} /></span>
                </span>
                <span className="mt-0.5 flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
                  <span className="rounded-full px-2 py-px text-[11px] font-semibold" style={pill(STATUS[o.status]?.color ?? "#64748b")}>{STATUS[o.status]?.label}</span>
                  <span className="flex items-center gap-1 rounded-full px-2 py-px font-medium"
                    style={o.deliveryDate <= (today ?? "") ? pill("#DC2626") : o.deliveryDate === tomorrow ? pill("#EA580C") : undefined}>
                    <Truck size={11} /> {when}
                  </span>
                  <span className="truncate">{o.number.replace("CMD-2026-", "n° ")} · {o.lineCount} lignes</span>
                </span>
              </Link>
              {next ? (
                <button disabled={step.isPending} onClick={() => step.mutate({ o })}
                  className="w-[84px] shrink-0 rounded-full bg-[#1F6BFF] py-1.5 text-[12px] font-semibold text-white shadow-sm transition hover:-translate-y-0.5 hover:bg-[#1857d6] disabled:opacity-50">
                  {next.label}
                </button>
              ) : null}
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

function ToCollect() {
  const qc = useQueryClient();
  const [asking, setAsking] = useState<string>();
  const [paid, setPaid] = useState<string[]>([]);
  const invoices = useQuery({
    queryKey: ["today", "invoices"],
    queryFn: async () => (await Promise.all(["overdue", "partially_paid", "issued"].map((status) => api.invoices.list({ status, limit: 200 } as never)))).flat(),
    ...LIVE,
  });
  const pay = useMutation({
    mutationFn: (inv: InvoiceSummary) => api.payments.create({
      clientId: inv.clientId, amount: Math.round(inv.balance * 100) / 100, method: "transfer",
      reference: `Virement reçu (${inv.number})`, allocations: [{ invoiceId: inv.id, amount: Math.round(inv.balance * 100) / 100 }],
    } as never),
    onSuccess: (_r, inv) => { setPaid((p) => [...p, inv.clientName ?? inv.number]); setAsking(undefined); },
    onSettled: () => void qc.invalidateQueries({ queryKey: ["today"] }),
  });
  const all = ((invoices.data ?? []) as InvoiceSummary[]).filter((i) => i.balance > 0)
    .sort((a, b) => (b.daysOverdue ?? 0) - (a.daysOverdue ?? 0) || b.balance - a.balance);
  return (
    <Card title="À encaisser" icon={Wallet} tone="#EF4444" count={all.filter((i) => i.status === "overdue").length} alert
      extra={paid.length ? <p className="mx-4 mb-2 flex items-center gap-1.5 rounded-lg bg-emerald-50 px-3 py-1.5 text-[12px] font-medium text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300"><Check size={13} /> Virement enregistré : {paid.join(", ")}</p> : null}>
      <ul className="space-y-0.5 px-2">
        {all.slice(0, 40).map((i) => (
          <li key={i.id} className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 text-[13px] transition hover:bg-muted">
            <Avatar id={i.clientId} name={i.clientName ?? "?"} />
            <Link to={`/invoices/${i.id}`} className="min-w-[90px] flex-1">
              <span className="block truncate font-semibold hover:text-[#1F6BFF]">{i.clientName}</span>
              <span className="block truncate text-[11.5px]">
                {i.daysOverdue ? <span className="font-medium" style={{ color: "#DC2626" }}>{i.daysOverdue} j de retard</span> : <span className="text-muted-foreground">échéance {i.dueDate.slice(8, 10)}/{i.dueDate.slice(5, 7)}</span>}
              </span>
            </Link>
            <span className="shrink-0 font-bold tabular-nums"><Money value={i.balance} /></span>
            {asking === i.id ? (
              <span className="flex shrink-0 gap-1">
                <button disabled={pay.isPending} onClick={() => pay.mutate(i)}
                  className="rounded-full bg-emerald-600 px-3 py-1.5 text-[12px] font-semibold text-white shadow-sm transition hover:bg-emerald-700">Confirmer</button>
                <button onClick={() => setAsking(undefined)} className="rounded-full bg-muted p-1.5 text-muted-foreground transition hover:text-foreground"><X size={13} /></button>
              </span>
            ) : (
              <button onClick={() => setAsking(i.id)}
                className="shrink-0 rounded-full border border-emerald-600/40 px-3 py-1.5 text-[12px] font-semibold text-emerald-700 transition hover:bg-emerald-600 hover:text-white dark:text-emerald-300">
                Virement reçu
              </button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function StockOuts({ low }: { low: { productId: string; name: string; available: number }[] }) {
  return (
    <Card title="Stocks à surveiller" icon={PackageX} tone="#E11D48" count={low.filter((s) => s.available <= 0).length} alert>
      <ul className="space-y-0.5 px-2">
        {low.map((s) => (
          <li key={s.productId}>
            <Link to={`/products/${s.productId}`} className="flex items-center gap-2.5 rounded-xl px-2 py-1.5 text-[13px] transition hover:bg-muted">
              <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.available <= 0 ? "#EF4444" : "#FB923C", boxShadow: s.available <= 0 ? "0 0 0 3px rgba(239,68,68,.2)" : undefined }} />
              <span className={cn("min-w-0 flex-1 truncate", s.available <= 0 && "font-semibold")} style={s.available <= 0 ? { color: "#B91C1C" } : undefined}>{s.name}</span>
              <span className="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold" style={s.available <= 0 ? { background: "#DC2626", color: "white" } : pill("#EA580C")}>
                {s.available <= 0 ? "RUPTURE" : `reste ${s.available}`}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}
