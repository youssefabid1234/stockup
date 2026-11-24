/** Accueil — KPIs (useDashboard), CA 30 j, top clients, stock bas, DLC proches, activité en direct. Everything links to its entity. */
import { useMemo, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Activity, AlertTriangle, ArrowUpRight, CalendarClock, ClipboardList, Euro, PackageX, Plus, ShoppingCart, TrendingUp, Truck, Users,
} from "lucide-react";
import type { ActivityEvent, Dashboard } from "@kit/shared";
import { cn } from "@/lib/cn";
import { fmtDateLong, parseDate } from "@/lib/format";
import { ACTOR_LABEL } from "@/lib/labels";
import { entityPath } from "@/lib/links";
import { useDashboard, useEvents, useStreamStatus } from "@/lib/queries";
import {
  ActorIcon, Button, DateLabel, Dot, EmptyState, Money, Page, PageBody, PageHeader, Qty, Section, Skeleton, Stat, StatGrid, isAiActor,
} from "@/ui";
import { RevenueChart } from "./revenue-chart";

export default function DashboardPage() {
  const navigate = useNavigate();
  const { data: d, isLoading, isError, refetch } = useDashboard();
  const status = useStreamStatus();

  return (
    <Page>
      <PageHeader
        title="Accueil"
        meta={
          <span className="flex items-center gap-2 text-[12px] text-muted-foreground">
            {d ? <span className="capitalize">{fmtDateLong(d.today)}</span> : null}
            <span className="flex items-center gap-1.5">
              <Dot tone={status === "live" ? "success" : status === "connecting" ? "warning" : "destructive"} pulse={status === "live"} />
              {status === "live" ? "En direct" : status === "connecting" ? "Connexion…" : "Hors ligne"}
            </span>
          </span>
        }
        actions={<Button variant="primary" icon={Plus} onClick={() => navigate("/orders?new=1")}>Nouvelle commande</Button>}
      />
      <PageBody flush>
        {isError && !d ? (
          <EmptyState icon={TrendingUp} title="Tableau de bord indisponible" description="L'API ne répond pas. Vérifiez que le serveur tourne sur le port 4000." action={<Button size="sm" onClick={() => refetch()}>Réessayer</Button>} />
        ) : (
          <>
            <Kpis d={d} loading={isLoading} />
            <div className="grid grid-cols-1 gap-8 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_360px]">
              <div className="flex min-w-0 flex-col gap-7">
                <RevenueSection d={d} />
                <div className="grid grid-cols-1 gap-7 lg:grid-cols-3">
                  <TopClients d={d} />
                  <LowStock d={d} />
                  <Expiring d={d} />
                </div>
              </div>
              <LiveActivity />
            </div>
          </>
        )}
      </PageBody>
    </Page>
  );
}

function Kpis({ d, loading }: { d?: Dashboard; loading: boolean }) {
  const navigate = useNavigate();
  const v = (node: ReactNode) => (loading || !d ? <Skeleton className="mt-1 h-5 w-20" /> : node);
  return (
    <StatGrid className="md:grid-cols-3 xl:grid-cols-6 [&>*:nth-child(-n+3)]:border-b [&>*]:border-border xl:[&>*]:border-b-0">
      <Stat icon={Euro} label="CA du jour" value={v(<Money value={d?.revenueToday} compact />)} hint="Livraisons du jour, HT" onClick={() => navigate("/orders?date=today")} />
      <Stat icon={TrendingUp} label="CA du mois" value={v(<Money value={d?.revenueMonth} compact />)} hint="Depuis le 1er, HT" onClick={() => navigate("/invoices")} />
      <Stat icon={ShoppingCart} label="Commandes du jour" value={v(<span className="num">{d?.ordersToday}</span>)} hint="Livraison aujourd'hui" onClick={() => navigate("/orders?date=today")} />
      <Stat
        icon={ClipboardList} label="Pré-commandes à traiter" value={v(<span className="num">{d?.draftOrders}</span>)}
        tone={d && d.draftOrders > 0 ? "violet" : undefined} hint="À confirmer" onClick={() => navigate("/orders?status=draft")}
      />
      <Stat icon={Truck} label="À livrer aujourd'hui" value={v(<span className="num">{d?.toDeliverToday}</span>)} hint="Confirmées ou préparées" onClick={() => navigate("/orders?date=today")} />
      <Stat
        icon={AlertTriangle} label="Impayés en retard" value={v(<Money value={d?.overdueInvoicesAmount} compact />)}
        tone={d && d.overdueInvoicesAmount > 0 ? "destructive" : undefined}
        hint={d ? `${d.overdueInvoicesCount} facture${d.overdueInvoicesCount > 1 ? "s" : ""}` : undefined}
        onClick={() => navigate("/invoices?status=overdue")}
      />
    </StatGrid>
  );
}

function RevenueSection({ d }: { d?: Dashboard }) {
  const navigate = useNavigate();
  const total = useMemo(() => d?.revenueByDay.reduce((s, x) => s + x.revenue, 0) ?? 0, [d]);
  const days = d?.revenueByDay.filter((x) => x.revenue > 0).length ?? 0;
  return (
    <Section
      title="Chiffre d'affaires · 30 jours"
      actions={d ? (
        <span className="flex items-center gap-3 text-[12px] text-muted-foreground">
          <span>Total <Money value={total} compact className="font-medium text-foreground" /></span>
          <span>Moyenne <Money value={days ? total / days : 0} compact className="font-medium text-foreground" /> / jour livré</span>
        </span>
      ) : null}
    >
      <div className="rounded-[6px] border border-border bg-card px-3 pb-1 pt-3">
        {d ? (
          d.revenueByDay.length ? (
            <RevenueChart data={d.revenueByDay} today={d.today} onPick={(date) => navigate(`/orders?date=${date}`)} />
          ) : (
            <EmptyState compact icon={TrendingUp} title="Pas encore de chiffre d'affaires" />
          )
        ) : (
          <Skeleton className="mb-2 h-[164px] w-full" />
        )}
      </div>
    </Section>
  );
}

function ListFrame({ children }: { children: ReactNode }) {
  return <ul className="flex flex-col divide-y divide-border overflow-hidden rounded-[6px] border border-border bg-card">{children}</ul>;
}
function ListSkeleton() {
  return <ListFrame>{Array.from({ length: 5 }).map((_, i) => <li key={i} className="flex h-9 items-center px-3"><Skeleton className="h-3 w-full" /></li>)}</ListFrame>;
}
function EmptyLine({ icon: Icon, text }: { icon: typeof Users; text: string }) {
  return (
    <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-border px-3 py-3 text-[12.5px] text-muted-foreground">
      <Icon size={14} strokeWidth={1.75} />{text}
    </div>
  );
}
const ROW = "flex h-9 items-center gap-2.5 px-3 text-[12.5px] transition-colors hover:bg-muted/60";

function TopClients({ d }: { d?: Dashboard }) {
  const top = d?.topClients.slice(0, 7) ?? [];
  const max = Math.max(1, ...top.map((c) => c.revenue));
  return (
    <Section title="Top clients · 30 j" actions={<SeeAll to="/clients" />}>
      {!d ? <ListSkeleton /> : top.length === 0 ? <EmptyLine icon={Users} text="Aucune vente sur la période." /> : (
        <ListFrame>
          {top.map((c, i) => (
            <li key={c.clientId}>
              <Link to={`/clients/${c.clientId}`} className={ROW}>
                <span className="num w-4 shrink-0 text-[11.5px] text-muted-foreground">{i + 1}</span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{c.name}</span>
                  <span className="mt-0.5 block h-[3px] overflow-hidden rounded-full bg-muted">
                    <span className="block h-full rounded-full bg-chart-1" style={{ width: `${Math.round((c.revenue / max) * 100)}%` }} />
                  </span>
                </span>
                <Money value={c.revenue} compact className="shrink-0" />
              </Link>
            </li>
          ))}
        </ListFrame>
      )}
    </Section>
  );
}

function LowStock({ d }: { d?: Dashboard }) {
  const rows = d?.lowStock.slice().sort((a, b) => a.available - b.available).slice(0, 7) ?? [];
  return (
    <Section title="Stock bas" count={d?.lowStock.length} actions={<SeeAll to="/stock" />}>
      {!d ? <ListSkeleton /> : rows.length === 0 ? <EmptyLine icon={PackageX} text="Aucun produit sous le seuil." /> : (
        <ListFrame>
          {rows.map((p) => (
            <li key={p.productId}>
              <Link to={`/products/${p.productId}`} className={ROW}>
                <Dot tone={p.available <= 0 ? "destructive" : "warning"} />
                <span className="min-w-0 flex-1 truncate">{p.name}</span>
                <Qty value={p.available} unit={p.unit} tone={p.available <= 0 ? "destructive" : "warning"} className="shrink-0" />
              </Link>
            </li>
          ))}
        </ListFrame>
      )}
    </Section>
  );
}

function daysBetween(from: string, to: string) {
  return Math.round((parseDate(to).getTime() - parseDate(from).getTime()) / 86_400_000);
}

function Expiring({ d }: { d?: Dashboard }) {
  const rows = d?.expiringSoon.slice().sort((a, b) => a.expiresAt.localeCompare(b.expiresAt)).slice(0, 7) ?? [];
  return (
    <Section title="DLC proches" count={d?.expiringSoon.length} actions={<SeeAll to="/stock" />}>
      {!d ? <ListSkeleton /> : rows.length === 0 ? <EmptyLine icon={CalendarClock} text="Aucun lot proche de sa date limite." /> : (
        <ListFrame>
          {rows.map((l) => {
            const n = daysBetween(d.today, l.expiresAt);
            const urgent = n <= 2;
            return (
              <li key={l.lotId}>
                <Link to={`/products/${l.productId}`} className={ROW}>
                  <span className="min-w-0 flex-1 truncate">{l.name}</span>
                  <Qty value={l.qtyRemaining} className="shrink-0 text-muted-foreground" />
                  <span className={cn("num w-[62px] shrink-0 text-right", urgent ? "font-medium text-warning" : "text-muted-foreground")} title={fmtDateLong(l.expiresAt)}>
                    {n < 0 ? "dépassée" : n === 0 ? "auj." : n === 1 ? "demain" : `J+${n}`}
                  </span>
                </Link>
              </li>
            );
          })}
        </ListFrame>
      )}
    </Section>
  );
}

function SeeAll({ to }: { to: string }) {
  return <Link to={to} className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground">Voir<ArrowUpRight size={12} /></Link>;
}

function LiveActivity() {
  const { data, isLoading } = useEvents(30);
  const events = (data ?? []).slice(0, 14);
  return (
    <aside className="min-w-0">
      <Section title="Activité en direct" actions={<SeeAll to="/activity" />}>
        {isLoading ? <ListSkeleton /> : events.length === 0 ? (
          <EmptyLine icon={Activity} text="Les commandes, paiements et appels de l'agent vocal s'afficheront ici en temps réel." />
        ) : (
          <ListFrame>{events.map((e) => <EventItem key={e.id} e={e} />)}</ListFrame>
        )}
      </Section>
    </aside>
  );
}

function EventItem({ e }: { e: ActivityEvent }) {
  const ai = isAiActor(e.actor);
  const to = entityPath(e.entity, e.entityId);
  const body = (
    <>
      {ai ? <span className="absolute inset-y-0 left-0 w-[2px] bg-violet" aria-hidden /> : null}
      <ActorIcon actor={e.actor} size={22} />
      <span className="min-w-0 flex-1">
        <span className="line-clamp-2 text-[12.5px] leading-[17px]">{e.summary}</span>
        <span className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className={cn(ai && "text-violet")}>{e.actorName || ACTOR_LABEL[e.actor]}</span>
          <span>·</span>
          <DateLabel date={e.at} format="relative" />
        </span>
      </span>
    </>
  );
  const cls = cn(
    "relative flex items-start gap-2.5 px-3 py-2 transition-colors animate-fade-in",
    ai ? "bg-violet/[.045] hover:bg-violet/[.08]" : "hover:bg-muted/60",
  );
  return <li>{to ? <Link to={to} className={cls}>{body}</Link> : <div className={cls}>{body}</div>}</li>;
}
