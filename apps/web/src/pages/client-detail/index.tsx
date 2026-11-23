/**
 * Client detail — REFERENCE DETAIL PAGE. Pattern:
 *  - PageHeader with breadcrumb + title + status meta + actions (mutations via useApiMutation),
 *  - StatGrid of KPIs under the header,
 *  - two columns: main sections (framed DataTables, `inset`) | 340px aside (KeyValue, contacts, notes),
 *  - inline edit (add note) instead of a modal,
 *  - skeleton while loading, EmptyState for 404 / empty sections.
 */
import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Ban, BookOpen, CheckCircle2, FileText, History, Mail, MessageSquarePlus, Phone, Plus, ShoppingCart, Tag, UserRound, Users } from "lucide-react";
import type { ClientDetail, InvoiceSummary, OrderSummary, UsualBasketLine } from "@kit/shared";
import { api } from "@/lib/api";
import { CLIENT_TYPE_LABEL, SOURCE_LABEL, WEEKDAY_LABEL, WEEKDAYS } from "@/lib/labels";
import { fmtPercent } from "@/lib/format";
import { qk, useApiMutation, useClient, useContextFor, useInvoicesPage } from "@/lib/queries";
import { ContextSummary, EntityContext } from "@/pages/context/shared";
import { useUrlState } from "@/lib/url-state";
import { TagEditor } from "@/ui/tags";
import { useCreateDocument } from "@/features/document/create";
import { GroupsStrip } from "@/pages/history/timeline";
import { ClientHistoryTab, ClientNewEventPanel, RecentHistory } from "@/pages/history/entity-history";
import {
  Badge, Button, DataTable, DateLabel, Dot, EmptyState, KeyValue, Money, Mono, Page, PageBody, PageHeader, Qty, Section,
  Skeleton, Stat, StatGrid, StatusDot, Tabs, Textarea, useServerList, type Column,
} from "@/ui";

export default function ClientDetailPage() {
  const { id = "" } = useParams();
  const { data: c, isLoading, isError } = useClient(id);

  if (isLoading) return <DetailSkeleton />;
  if (isError || !c) {
    return (
      <Page>
        <PageHeader breadcrumb={[{ label: "Clients", to: "/clients" }]} title={id} />
        <PageBody><EmptyState icon={Users} title="Client introuvable" description={`Aucun client ne correspond à l'identifiant ${id}.`} /></PageBody>
      </Page>
    );
  }
  return <ClientView c={c} />;
}

function ClientView({ c }: { c: ClientDetail }) {
  const newOrder = useCreateDocument("sale");
  const setStatus = useApiMutation((status: ClientDetail["status"]) => api.clients.update(c.id, { status }), {
    success: (u) => (u.status === "blocked" ? "Client bloqué" : "Client réactivé"),
    invalidate: [qk.clients.all],
  });
  const creditUse = c.creditLimit > 0 ? c.outstanding / c.creditLimit : 0;
  const [tab, setTab] = useUrlState("tab", "overview");
  const [newEvent, setNewEvent] = useUrlState("newEvent", "", { keepPage: true });
  const [newCtx, setNewCtx] = useUrlState("newCtx", "", { keepPage: true });
  const { data: ctx } = useContextFor("client", c.id);

  return (
    <Page>
      <PageHeader
        breadcrumb={[{ label: "Clients", to: "/clients" }]}
        title={c.name}
        meta={
          <>
            <Mono className="text-muted-foreground">{c.code}</Mono>
            <StatusDot kind="client" value={c.status} />
          </>
        }
        tabs={
          <Tabs
            value={tab as "overview" | "history" | "context"}
            onChange={setTab}
            items={[
              { id: "overview", label: "Vue d'ensemble" },
              { id: "history", label: c.eventStats.open ? <>Historique <Dot tone="warning" /></> : "Historique", count: c.eventStats.total },
              { id: "context", label: "Contexte", count: ctx?.entries.length },
            ]}
          />
        }
        actions={
          tab === "history" ? (
            <Button variant="primary" icon={History} onClick={() => setNewEvent("1")}>Nouvel événement</Button>
          ) : tab === "context" ? (
            <Button variant="primary" icon={BookOpen} onClick={() => setNewCtx("1")}>Nouvelle fiche</Button>
          ) : <>
            {c.status === "blocked" ? (
              <Button icon={CheckCircle2} loading={setStatus.isPending} onClick={() => setStatus.mutate("active")}>Débloquer</Button>
            ) : (
              <Button variant="danger" icon={Ban} loading={setStatus.isPending} onClick={() => setStatus.mutate("blocked")}>Bloquer</Button>
            )}
            <Button variant="primary" icon={Plus} loading={newOrder.isPending} onClick={() => newOrder.mutate(c.id)}>
              Nouvelle commande
            </Button>
          </>
        }
      />
      <PageBody flush>
        <GroupsStrip><TagEditor scope="client" value={c.tags} entityId={c.id} /></GroupsStrip>
        {tab === "history" ? <ClientHistoryTab c={c} /> : tab === "context" ? (
          <EntityContext scope="client" id={c.id} label={c.name} layout="tab" newOpen={!!newCtx} onNewClose={() => setNewCtx("")} />
        ) : <>
        <StatGrid className="md:grid-cols-5">
          <Stat label="Encours" value={<Money value={c.outstanding} />} hint={c.creditLimit ? `${fmtPercent(creditUse)} du plafond` : "Pas de plafond"} tone={creditUse > 0.9 ? "warning" : undefined} />
          <Stat label="En retard" value={<Money value={c.overdue} />} tone={c.overdue > 0 ? "destructive" : undefined} hint={`${c.openInvoiceCount} facture${c.openInvoiceCount > 1 ? "s" : ""} ouverte${c.openInvoiceCount > 1 ? "s" : ""}`} />
          <Stat label="CA 30 jours" value={<Money value={c.revenue30d} compact />} />
          <Stat label="Dernière commande" value={<DateLabel date={c.lastOrderAt} />} hint={c.lastOrderAt ? <DateLabel date={c.lastOrderAt} format="relative" /> : undefined} />
          <Stat label="Plafond de crédit" value={<Money value={c.creditLimit} compact />} hint={c.paymentTermsDays ? `Paiement à ${c.paymentTermsDays} j` : "Comptant à la livraison"} />
        </StatGrid>

        <div className="grid grid-cols-1 gap-8 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex min-w-0 flex-col gap-7">
            <UsualBasket lines={c.usual} />
            <RecentOrders orders={c.recentOrders} />
            <OpenInvoices c={c} />
            <NegotiatedPrices prices={c.prices} />
          </div>
          <aside className="flex min-w-0 flex-col gap-7">
            <Section title="Informations">
              <KeyValue
                labelWidth={120}
                items={[
                  { label: "Type", value: CLIENT_TYPE_LABEL[c.type] },
                  { label: "Adresse", value: c.address ? <>{c.address}<br />{c.city}</> : c.city || "—" },
                  { label: "Zone", value: c.zone || "—" },
                  { label: "Jours de livraison", value: <DeliveryDays days={c.deliveryDays} /> },
                  { label: "Conditions", value: c.paymentTermsDays ? `${c.paymentTermsDays} jours` : "Comptant" },
                  { label: "Commercial", value: c.salesRep || "—" },
                  { label: "Client depuis", value: <DateLabel date={c.createdAt} format="long" /> },
                ]}
              />
              {c.preferences ? (
                <div className="mt-3 rounded-[4px] border border-border bg-muted/40 px-3 py-2 text-[12.5px] text-secondary-foreground">{c.preferences}</div>
              ) : null}
            </Section>
            <ContextSummary data={ctx} onOpen={() => setTab("context")} />
            <RecentHistory kind="client" events={c.recentEvents} stats={c.eventStats} onOpen={() => setTab("history")} />
            <Contacts contacts={c.contacts} />
            <Notes clientId={c.id} notes={c.notes} />
          </aside>
        </div>
        </>}
      </PageBody>
      {newEvent ? <ClientNewEventPanel c={c} onClose={() => setNewEvent("")} /> : null}
    </Page>
  );
}

function DeliveryDays({ days }: { days: ClientDetail["deliveryDays"] }) {
  return (
    <span className="inline-flex gap-1">
      {WEEKDAYS.slice(0, 6).map((d) => (
        <span key={d} className={days.includes(d) ? "font-medium text-foreground" : "text-muted-foreground/50"}>{WEEKDAY_LABEL[d].replace(".", "")}</span>
      ))}
    </span>
  );
}

// ── Sections ──
const USUAL_COLS: Column<UsualBasketLine>[] = [
  { id: "product", header: "Produit", cell: (l) => <span className="font-medium">{l.productName}</span> },
  { id: "freq", header: "Fréquence", width: 140, cell: (l) => <Frequency value={l.frequency} /> },
  { id: "avg", header: "Qté moyenne", width: 110, numeric: true, cell: (l) => <Qty value={l.avgQty} unit={l.unit} /> },
  { id: "last", header: "Dernière qté", width: 110, numeric: true, cell: (l) => <Qty value={l.lastQty} unit={l.unit} /> },
  { id: "when", header: "Dernière fois", width: 120, cell: (l) => <DateLabel date={l.lastOrderedAt} className="text-muted-foreground" /> },
];
function Frequency({ value }: { value: number }) {
  return (
    <span className="flex items-center gap-2">
      <span className="h-1 w-16 overflow-hidden rounded-full bg-muted"><span className="block h-full rounded-full bg-primary" style={{ width: `${Math.round(value * 100)}%` }} /></span>
      <span className="num text-[12px] text-muted-foreground">{fmtPercent(value)}</span>
    </span>
  );
}
function UsualBasket({ lines }: { lines: UsualBasketLine[] }) {
  return (
    <Section title="Panier habituel" count={lines.length}>
      <DataTable inset paginate={false} columns={USUAL_COLS} rows={lines} getRowId={(l) => l.productId}
        empty={<EmptyFrame icon={ShoppingCart} text="Pas encore assez d'historique pour un panier habituel." />} />
    </Section>
  );
}

const ORDER_COLS: Column<OrderSummary>[] = [
  { id: "number", header: "N°", width: 160, cell: (o) => <Mono>{o.number}</Mono> },
  { id: "date", header: "Livraison", width: 120, cell: (o) => <DateLabel date={o.deliveryDate} /> },
  { id: "source", header: "Canal", cell: (o) => (o.source === "voice_agent" ? <Badge tone="violet">{SOURCE_LABEL[o.source]}</Badge> : <span className="text-muted-foreground">{SOURCE_LABEL[o.source] ?? o.source}</span>) },
  { id: "lines", header: "Lignes", width: 70, numeric: true, muted: true, cell: (o) => o.lineCount },
  { id: "total", header: "Total HT", width: 110, numeric: true, cell: (o) => <Money value={o.totalHt} /> },
  { id: "status", header: "Statut", width: 110, cell: (o) => <StatusDot kind="order" value={o.status} /> },
];
function RecentOrders({ orders }: { orders: OrderSummary[] }) {
  const navigate = useNavigate();
  return (
    <Section title="Commandes récentes" count={orders.length}>
      <DataTable inset pageKey="ordersPage" columns={ORDER_COLS} rows={orders} getRowId={(o) => o.id} onRowClick={(o) => navigate(`/orders/${o.id}`)}
        empty={<EmptyFrame icon={ShoppingCart} text="Aucune commande pour ce client." />} />
    </Section>
  );
}

const INVOICE_COLS: Column<InvoiceSummary>[] = [
  { id: "number", header: "N°", width: 160, cell: (i) => <Mono>{i.number}</Mono> },
  { id: "issued", header: "Émise", width: 110, cell: (i) => <DateLabel date={i.issuedAt} /> },
  { id: "due", header: "Échéance", cell: (i) => (
      <span className={i.daysOverdue > 0 ? "text-destructive" : undefined}>
        <DateLabel date={i.dueDate} />{i.daysOverdue > 0 ? <span className="ml-1.5 text-[12px]">+{i.daysOverdue} j</span> : null}
      </span>
    ) },
  { id: "ttc", header: "TTC", width: 110, numeric: true, cell: (i) => <Money value={i.totalTtc} /> },
  { id: "balance", header: "Reste dû", width: 110, numeric: true, cell: (i) => <Money value={i.balance} tone={i.daysOverdue > 0 ? "destructive" : undefined} /> },
  { id: "status", header: "Statut", width: 150, cell: (i) => <StatusDot kind="invoice" value={i.status} /> },
];
/** Every open invoice of the client, oldest due first, one server page at a time (the detail embeds at most 100). */
function OpenInvoices({ c }: { c: ClientDetail }) {
  const navigate = useNavigate();
  const list = useServerList({ pageKey: "invoicesPage", sortKey: "invoicesSort", defaultSort: { id: "due", dir: "asc" } });
  const { data } = useInvoicesPage({ clientId: c.id, status: "open", ...list.params });
  const count = data?.total ?? c.openInvoiceCount;
  const total = data?.sums?.balance ?? c.outstanding;
  return (
    <Section title="Factures ouvertes" count={count} actions={count ? <span className="text-[12px] text-muted-foreground">Total <Money value={total} className="font-medium text-foreground" /></span> : null}>
      <DataTable inset server={{ list, total: data?.total }} columns={INVOICE_COLS} rows={data?.items ?? c.openInvoices.slice(0, 100)}
        getRowId={(i) => i.id} onRowClick={(i) => navigate(`/invoices/${i.id}`)}
        empty={<EmptyFrame icon={FileText} text="Aucune facture en attente de paiement." />} />
    </Section>
  );
}

type PriceRow = ClientDetail["prices"][number];
const PRICE_COLS: Column<PriceRow>[] = [
  { id: "product", header: "Produit", cell: (p) => p.productName },
  { id: "list", header: "Prix catalogue", width: 120, numeric: true, muted: true, cell: (p) => <Money value={p.listPrice} /> },
  { id: "price", header: "Prix négocié", width: 120, numeric: true, cell: (p) => <Money value={p.price} className="font-medium" /> },
  { id: "disc", header: "Remise", width: 90, numeric: true, cell: (p) => {
      const d = p.listPrice ? 1 - p.price / p.listPrice : 0;
      return <span className={d > 0 ? "text-success" : "text-muted-foreground"}>{d > 0 ? `−${fmtPercent(d)}` : "—"}</span>;
    } },
];
function NegotiatedPrices({ prices }: { prices: PriceRow[] }) {
  return (
    <Section title="Prix négociés" count={prices.length}>
      <DataTable inset pageKey="pricesPage" columns={PRICE_COLS} rows={prices} getRowId={(p) => p.productId}
        empty={<EmptyFrame icon={Tag} text="Ce client paie le prix catalogue." />} />
    </Section>
  );
}

function Contacts({ contacts }: { contacts: ClientDetail["contacts"] }) {
  return (
    <Section title="Contacts" count={contacts.length}>
      {contacts.length === 0 ? (
        <div className="text-[12.5px] text-muted-foreground">Aucun contact renseigné.</div>
      ) : (
        <ul className="flex flex-col divide-y divide-border rounded-[6px] border border-border bg-card">
          {contacts.map((ct, i) => (
            <li key={i} className="flex items-start gap-2.5 px-3 py-2.5">
              <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground"><UserRound size={13} strokeWidth={1.75} /></span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5"><span className="font-medium">{ct.name}</span>{ct.role ? <span className="text-[12px] text-muted-foreground">· {ct.role}</span> : null}</div>
                <div className="mt-0.5 flex flex-wrap gap-x-3 gap-y-0.5 text-[12px] text-muted-foreground">
                  {ct.phone ? <a href={`tel:${ct.phone}`} className="inline-flex items-center gap-1 hover:text-foreground"><Phone size={11} />{ct.phone}</a> : null}
                  {ct.email ? <a href={`mailto:${ct.email}`} className="inline-flex items-center gap-1 truncate hover:text-foreground"><Mail size={11} />{ct.email}</a> : null}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}

function Notes({ clientId, notes }: { clientId: string; notes: ClientDetail["notes"] }) {
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const add = useApiMutation((t: string) => api.clients.addNote(clientId, { text: t, author: "Moi" }), {
    success: "Note ajoutée",
    invalidate: [qk.clients.detail(clientId)],
    onSuccess: () => { setText(""); setOpen(false); },
  });
  const sorted = [...notes].sort((a, b) => b.at.localeCompare(a.at));
  const submit = () => { if (text.trim()) add.mutate(text.trim()); };

  return (
    <Section title="Notes CRM" count={notes.length} actions={!open ? <Button size="sm" variant="ghost" icon={MessageSquarePlus} onClick={() => setOpen(true)}>Ajouter</Button> : null}>
      {open ? (
        <div className="mb-3 flex flex-col gap-2">
          <Textarea
            autoFocus
            rows={3}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
              if (e.key === "Escape") { e.preventDefault(); setOpen(false); }
            }}
            placeholder="Ex. : ne veut jamais de substitution sur le bar"
          />
          <div className="flex items-center justify-end gap-2">
            <span className="mr-auto text-[11.5px] text-muted-foreground">⌘↵ pour enregistrer</span>
            <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Annuler</Button>
            <Button size="sm" variant="primary" loading={add.isPending} disabled={!text.trim()} onClick={submit}>Enregistrer</Button>
          </div>
        </div>
      ) : null}
      {sorted.length === 0 && !open ? (
        <div className="text-[12.5px] text-muted-foreground">Aucune note. Consignez ici les habitudes et consignes du client.</div>
      ) : (
        <ol className="flex flex-col gap-3">
          {sorted.map((n, i) => (
            <li key={`${n.at}-${i}`} className="border-l-2 border-border pl-3">
              <div className="whitespace-pre-wrap text-[13px] leading-[19px]">{n.text}</div>
              <div className="mt-1 text-[11.5px] text-muted-foreground">{n.author} · <DateLabel date={n.at} format="relative" /></div>
            </li>
          ))}
        </ol>
      )}
    </Section>
  );
}

function EmptyFrame({ icon: Icon, text }: { icon: typeof Users; text: string }) {
  return (
    <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-border px-3 py-3 text-[12.5px] text-muted-foreground">
      <Icon size={14} strokeWidth={1.75} />{text}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <Page>
      <PageHeader breadcrumb={[{ label: "Clients", to: "/clients" }]} title={<Skeleton className="h-4 w-48" />} />
      <PageBody flush>
        <StatGrid className="md:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => <Stat key={i} label={<Skeleton className="h-3 w-20" />} value={<Skeleton className="mt-1 h-5 w-24" />} />)}
        </StatGrid>
        <div className="grid grid-cols-1 gap-8 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex flex-col gap-3">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-7 w-full" />)}</div>
          <div className="flex flex-col gap-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-4 w-full" />)}</div>
        </div>
      </PageBody>
    </Page>
  );
}
