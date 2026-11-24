/**
 * Team 12 (Youssef) · « Aujourd'hui » : the wholesaler's home, only what matters today, all actionable in place.
 *   who contacted us today · orders in progress (quotes → confirm → prepared → delivered) · what to collect, with
 *   « Virement reçu » · stock-outs in red. Everything older or detailed sits behind one button (« Historique et détails »).
 */
import { useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bot, Check, ChevronRight, History, PackageX, Phone, ShoppingCart, Truck, Wallet } from "lucide-react";
import type { InvoiceSummary, OrderSummary } from "@kit/shared";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fmtDateLong } from "@/lib/format";
import { Button, Dot, Money, Page, PageBody, PageHeader } from "@/ui";

const LIVE = { refetchInterval: 5000 };
const STEP: Record<string, { label: string; run: (id: string) => Promise<unknown> } | undefined> = {
  draft: { label: "Confirmer", run: api.orders.confirm },
  confirmed: { label: "Préparée", run: (id) => api.orders.prepare(id) },
  prepared: { label: "Livrée", run: api.orders.deliver },
};
const STATUS_FR: Record<string, string> = { draft: "Devis", confirmed: "Confirmée", prepared: "Préparée" };
const items = <T,>(d: unknown): T[] => (Array.isArray(d) ? d : ((d as { items?: T[] })?.items ?? []));

export default function TodayPage() {
  const navigate = useNavigate();
  const dash = useQuery({ queryKey: ["today", "dashboard"], queryFn: api.dashboard, ...LIVE });
  const today = dash.data?.today;
  return (
    <Page>
      <PageHeader
        title="Aujourd'hui"
        meta={<span className="text-[12px] capitalize text-muted-foreground">{today ? fmtDateLong(today) : ""}</span>}
        actions={
          <div className="flex gap-2">
            <Button icon={Phone} onClick={() => navigate("/voice")}>Standard (Lucie)</Button>
            <Button icon={History} onClick={() => navigate("/dashboard")}>Historique et détails</Button>
          </div>
        }
      />
      <PageBody flush>
        <Strip d={dash.data} />
        <div className="grid grid-cols-1 gap-4 p-4 lg:grid-cols-[0.9fr_1.5fr_1.1fr]">
          <Contacts today={today} />
          <Orders today={today} />
          <div className="flex min-w-0 flex-col gap-4">
            <ToCollect />
            <StockOuts d={dash.data} />
          </div>
        </div>
      </PageBody>
    </Page>
  );
}

function Card({ title, icon: Icon, count, tone, children }: { title: string; icon: typeof Phone; count?: number; tone?: string; children: ReactNode }) {
  return (
    <section className="flex min-h-0 min-w-0 flex-col rounded-[8px] border border-border bg-card">
      <h2 className="flex items-center gap-2 border-b border-border px-3 py-2 text-[12.5px] font-semibold">
        <Icon size={14} className={tone} /> {title}
        {count != null ? <span className={cn("ml-auto rounded-full px-2 text-[11px]", tone ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground")}>{count}</span> : null}
      </h2>
      <div className="max-h-[calc(100vh-230px)] min-h-0 overflow-y-auto">{children}</div>
    </section>
  );
}

function Strip({ d }: { d?: Awaited<ReturnType<typeof api.dashboard>> }) {
  const cell = (label: string, value: ReactNode, tone?: string) => (
    <div className="flex flex-col px-4 py-2">
      <span className="text-[11px] uppercase tracking-wide text-muted-foreground">{label}</span>
      <span className={cn("text-[18px] font-semibold tabular-nums", tone)}>{value}</span>
    </div>
  );
  const outs = d?.lowStock.filter((s) => s.available <= 0).length ?? 0;
  return (
    <div className="grid grid-cols-2 divide-x divide-border border-b border-border md:grid-cols-5">
      {cell("CA du jour", d ? <Money value={d.revenueToday} /> : "…")}
      {cell("À livrer aujourd'hui", d?.toDeliverToday ?? "…")}
      {cell("Devis à valider", d?.draftOrders ?? "…")}
      {cell("Impayés en retard", d ? <><Money value={d.overdueInvoicesAmount} /> <span className="text-[12px] font-normal">({d.overdueInvoicesCount})</span></> : "…", "text-destructive")}
      {cell("Ruptures", outs, outs ? "text-destructive" : undefined)}
    </div>
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
      else byClient.set(e.entityId, { id: e.entityId, name, last: e.summary.replace(/^.*?: /, ""), at: e.at, n: 1, ai: e.actor === "voice_agent" });
    }
    return [...byClient.values()];
  }, [events.data, today, clients.data]);
  return (
    <Card title="Qui nous a contacté aujourd'hui" icon={Phone} count={rows.length}>
      {rows.length === 0 ? <p className="p-3 text-[12px] text-muted-foreground">{events.isPending ? "Chargement…" : "Personne pour l'instant."}</p> : null}
      <ul className="divide-y divide-border">
        {rows.map((r) => (
          <li key={r.id}>
            <Link to={`/clients/${r.id}`} className="flex items-start gap-2 px-3 py-2 hover:bg-muted/60">
              <span className="mt-0.5 text-muted-foreground">{r.ai ? <Bot size={14} /> : <Phone size={14} />}</span>
              <span className="min-w-0 flex-1">
                <span className="flex items-center gap-2 text-[12.5px] font-medium">{r.name}
                  <span className="text-[11px] font-normal text-muted-foreground">{r.at.slice(11, 16)}{r.n > 1 ? ` · ${r.n} échanges` : ""}</span>
                </span>
                <span className="block truncate text-[11.5px] text-muted-foreground">{r.last}</span>
              </span>
              <ChevronRight size={14} className="mt-1 text-muted-foreground" />
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}

function Orders({ today }: { today?: string }) {
  const qc = useQueryClient();
  const [filter, setFilter] = useState<"all" | "draft" | "soon">("all");
  const orders = useQuery({
    queryKey: ["today", "orders"],
    queryFn: async () => (await Promise.all(["draft", "confirmed", "prepared"].map((status) => api.orders.list({ status, limit: 200 } as never)))).flat(),
    ...LIVE,
  });
  const step = useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) => STEP[status]!.run(id),
    onSettled: () => void qc.invalidateQueries({ queryKey: ["today"] }),
  });
  const tomorrow = today ? new Date(Date.parse(today) + 86400000).toISOString().slice(0, 10) : "";
  const all = (orders.data ?? []) as OrderSummary[];
  const shown = all
    .filter((o) => filter === "all" || (filter === "draft" ? o.status === "draft" : o.deliveryDate <= tomorrow))
    .sort((a, b) => a.deliveryDate.localeCompare(b.deliveryDate))
    .slice(0, 60);
  const tab = (key: typeof filter, label: string, n: number) => (
    <button onClick={() => setFilter(key)} className={cn("rounded-full px-2.5 py-0.5 text-[11.5px]", filter === key ? "bg-foreground text-background" : "bg-muted text-muted-foreground hover:text-foreground")}>
      {label} {n}
    </button>
  );
  return (
    <Card title="Commandes en cours" icon={ShoppingCart} count={all.length}>
      <div className="flex gap-1.5 border-b border-border px-3 py-2">
        {tab("all", "Toutes", all.length)}
        {tab("soon", "Livraison aujourd'hui / demain", all.filter((o) => o.deliveryDate <= tomorrow).length)}
        {tab("draft", "Devis", all.filter((o) => o.status === "draft").length)}
      </div>
      <ul className="divide-y divide-border">
        {shown.map((o) => {
          const next = STEP[o.status];
          const urgent = o.deliveryDate <= (today ?? "");
          return (
            <li key={o.id} className="flex items-center gap-2 px-3 py-1.5 text-[12.5px]">
              <Link to={`/orders/${o.id}`} className="min-w-0 flex-1 hover:underline">
                <span className="block truncate font-medium">{o.clientName}</span>
                <span className="block truncate text-[11px] text-muted-foreground">{o.number.replace("CMD-2026-", "n° ")} · {o.lineCount} lignes</span>
              </Link>
              <span className={cn("shrink-0 text-[11.5px] tabular-nums", urgent ? "font-semibold text-destructive" : o.deliveryDate === tomorrow ? "text-warning" : "text-muted-foreground")}>
                <Truck size={11} className="mr-1 inline" />{o.deliveryDate === today ? "aujourd'hui" : o.deliveryDate === tomorrow ? "demain" : o.deliveryDate.slice(8, 10) + "/" + o.deliveryDate.slice(5, 7)}
              </span>
              <span className="w-[82px] shrink-0 text-right tabular-nums"><Money value={o.totalHt} /></span>
              <span className={cn("w-[66px] shrink-0 rounded px-1.5 text-center text-[11px]", o.status === "draft" ? "bg-warning/15 text-warning" : "bg-muted text-muted-foreground")}>{STATUS_FR[o.status]}</span>
              {next ? (
                <Button size="sm" className="w-[78px] shrink-0" disabled={step.isPending} onClick={() => step.mutate({ id: o.id, status: o.status })}>{next.label}</Button>
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
    onSuccess: (_r, inv) => { setPaid((p) => [...p, inv.number]); setAsking(undefined); },
    onSettled: () => void qc.invalidateQueries({ queryKey: ["today"] }),
  });
  const all = ((invoices.data ?? []) as InvoiceSummary[]).filter((i) => i.balance > 0)
    .sort((a, b) => (b.daysOverdue ?? 0) - (a.daysOverdue ?? 0) || b.balance - a.balance);
  return (
    <Card title="À encaisser" icon={Wallet} count={all.filter((i) => i.status === "overdue").length} tone="text-destructive">
      {paid.length ? <p className="border-b border-border px-3 py-1.5 text-[11.5px] text-success"><Check size={12} className="mr-1 inline" />Encaissé : {paid.join(", ")}</p> : null}
      <ul className="divide-y divide-border">
        {all.slice(0, 40).map((i) => (
          <li key={i.id} className="flex items-center gap-2 px-3 py-1.5 text-[12.5px]">
            <Link to={`/invoices/${i.id}`} className="min-w-0 flex-1 hover:underline">
              <span className="font-medium">{i.clientName}</span>
              <span className="block text-[11px] text-muted-foreground">{i.number} · {i.daysOverdue ? <span className="text-destructive">{i.daysOverdue} j de retard</span> : `échéance ${i.dueDate.slice(8, 10)}/${i.dueDate.slice(5, 7)}`}</span>
            </Link>
            <span className="shrink-0 tabular-nums font-medium"><Money value={i.balance} /></span>
            {asking === i.id ? (
              <span className="flex shrink-0 gap-1">
                <Button size="sm" variant="primary" disabled={pay.isPending} onClick={() => pay.mutate(i)}>Confirmer</Button>
                <Button size="sm" onClick={() => setAsking(undefined)}>✕</Button>
              </span>
            ) : (
              <Button size="sm" className="shrink-0" onClick={() => setAsking(i.id)}>Virement reçu</Button>
            )}
          </li>
        ))}
      </ul>
    </Card>
  );
}

function StockOuts({ d }: { d?: Awaited<ReturnType<typeof api.dashboard>> }) {
  const low = d?.lowStock ?? [];
  return (
    <Card title="Stocks à surveiller" icon={PackageX} count={low.filter((s) => s.available <= 0).length} tone="text-destructive">
      <ul className="divide-y divide-border">
        {low.map((s) => (
          <li key={s.productId}>
            <Link to={`/products/${s.productId}`} className="flex items-center gap-2 px-3 py-1.5 text-[12.5px] hover:bg-muted/60">
              <Dot tone={s.available <= 0 ? "destructive" : "warning"} />
              <span className={cn("min-w-0 flex-1 truncate", s.available <= 0 && "font-medium text-destructive")}>{s.name}</span>
              <span className={cn("shrink-0 text-[11.5px]", s.available <= 0 ? "font-semibold text-destructive" : "text-warning")}>
                {s.available <= 0 ? "RUPTURE" : `reste ${s.available}`}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Card>
  );
}
