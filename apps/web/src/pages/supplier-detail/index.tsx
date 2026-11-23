/** Fournisseur — info + contacts, price list, purchase order history, "Commander" (creates an empty draft for this supplier and opens it). */
import { useNavigate, useParams } from "react-router-dom";
import { BookOpen, History, Mail, Phone, Plus, ShoppingBasket, Tag, Truck, UserRound } from "lucide-react";
import type { PurchaseOrderSummary, SupplierDetail } from "@kit/shared";
import { categoryIds, categoryLabel, categoryOptions } from "@/lib/labels";
import { UNIT_LABEL } from "@/lib/format";
import { useContextFor, usePurchaseOrdersPage, useSupplier } from "@/lib/queries";
import { ContextSummary, EntityContext } from "@/pages/context/shared";
import { useUrlState } from "@/lib/url-state";
import { TagEditor } from "@/ui/tags";
import { GroupsStrip } from "@/pages/history/timeline";
import { RecentHistory, SupplierHistoryTab, SupplierNewEventPanel } from "@/pages/history/entity-history";
import {
  Badge, Button, DataTable, DateLabel, EmptyState, KeyValue, Money, Mono, Page, PageBody, PageHeader, Section, Skeleton, Stat,
  StatGrid, StatusDot, Tabs, Dot, useServerList, type Column,
} from "@/ui";
import { useCreateDocument } from "@/features/document/create";

export default function SupplierDetailPage() {
  const { id = "" } = useParams();
  const { data: s, isLoading, isError } = useSupplier(id);

  if (isLoading) return <DetailSkeleton />;
  if (isError || !s) {
    return (
      <Page>
        <PageHeader breadcrumb={[{ label: "Fournisseurs", to: "/suppliers" }]} title={id} />
        <PageBody><EmptyState icon={Truck} title="Fournisseur introuvable" description={`Aucun fournisseur ne correspond à l'identifiant ${id}.`} /></PageBody>
      </Page>
    );
  }
  return <SupplierView s={s} />;
}

function SupplierView({ s }: { s: SupplierDetail }) {
  const order = useCreateDocument("purchase");
  const [tab, setTab] = useUrlState("tab", "overview");
  const [newEvent, setNewEvent] = useUrlState("newEvent", "", { keepPage: true });
  const [newCtx, setNewCtx] = useUrlState("newCtx", "", { keepPage: true });
  const { data: ctx } = useContextFor("supplier", s.id);
  const st = s.purchaseStats; // over ALL purchase orders (the detail only embeds the latest 60)

  return (
    <Page>
      <PageHeader
        breadcrumb={[{ label: "Fournisseurs", to: "/suppliers" }]}
        title={s.name}
        meta={
          <>
            <span className="text-[12.5px] text-muted-foreground">{s.city}</span>
          </>
        }
        tabs={
          <Tabs
            value={tab as "overview" | "history" | "context"}
            onChange={setTab}
            items={[
              { id: "overview", label: "Vue d'ensemble" },
              { id: "history", label: s.eventStats.open ? <>Historique <Dot tone="warning" /></> : "Historique", count: s.eventStats.total },
              { id: "context", label: "Contexte", count: ctx?.entries.length },
            ]}
          />
        }
        actions={
          tab === "history" ? (
            <Button variant="primary" icon={History} onClick={() => setNewEvent("1")}>Nouvel événement</Button>
          ) : tab === "context" ? (
            <Button variant="primary" icon={BookOpen} onClick={() => setNewCtx("1")}>Nouvelle fiche</Button>
          ) : (
            <Button variant="primary" icon={Plus} loading={order.isPending} onClick={() => order.mutate(s.id)}>Commander</Button>
          )
        }
      />
      <PageBody flush>
        <GroupsStrip><TagEditor scope="supplier" value={s.tags} entityId={s.id} /></GroupsStrip>
        {tab === "history" ? <SupplierHistoryTab s={s} /> : tab === "context" ? (
          <EntityContext scope="supplier" id={s.id} label={s.name} layout="tab" newOpen={!!newCtx} onNewClose={() => setNewCtx("")} />
        ) : <>
        <StatGrid className="md:grid-cols-5">
          <Stat label="Délai de livraison" value={`${s.leadTimeDays} j`} />
          <Stat label="Conditions" value={s.paymentTermsDays ? `${s.paymentTermsDays} j` : "Comptant"} hint="Délai de paiement" />
          <Stat label="Minimum de commande" value={<Money value={s.minOrderAmount} compact />} />
          <Stat label="En cours" value={<Money value={st.openTotal} compact />} tone={st.openCount ? "info" : undefined}
            hint={`${st.openCount} commande${st.openCount > 1 ? "s" : ""}${st.draftCount ? ` · ${st.draftCount} brouillon${st.draftCount > 1 ? "s" : ""}` : ""}`} />
          <Stat label="Total acheté" value={<Money value={st.doneTotal} compact />} hint={`${st.doneCount} commande${st.doneCount > 1 ? "s" : ""}`} />
        </StatGrid>

        <div className="grid grid-cols-1 gap-8 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex min-w-0 flex-col gap-7">
            <PriceList prices={s.prices} />
            <PurchaseOrders supplierId={s.id} onOrder={() => order.mutate(s.id)} />
          </div>
          <aside className="flex min-w-0 flex-col gap-7">
            <Section title="Informations">
              <KeyValue
                labelWidth={120}
                items={[
                  { label: "Ville", value: s.city || "—" },
                  { label: "Catégories", value: s.categories.length ? <span className="flex flex-wrap gap-1">{s.categories.map((c) => <Badge key={c}>{categoryLabel(c)}</Badge>)}</span> : "—" },
                  { label: "Délai", value: `${s.leadTimeDays} jour${s.leadTimeDays > 1 ? "s" : ""}` },
                  { label: "Paiement", value: s.paymentTermsDays ? `${s.paymentTermsDays} jours` : "Comptant" },
                  { label: "Minimum", value: <Money value={s.minOrderAmount} /> },
                ]}
              />
              {s.notes ? <div className="mt-3 rounded-[4px] border border-border bg-muted/40 px-3 py-2 text-[12.5px] text-secondary-foreground">{s.notes}</div> : null}
            </Section>
            <ContextSummary data={ctx} onOpen={() => setTab("context")} />
            <RecentHistory kind="supplier" events={s.recentEvents} stats={s.eventStats} onOpen={() => setTab("history")} />
            <Contacts contacts={s.contacts} />
          </aside>
        </div>
        </>}
      </PageBody>
      {newEvent ? <SupplierNewEventPanel s={s} onClose={() => setNewEvent("")} /> : null}
    </Page>
  );
}

type PriceRow = SupplierDetail["prices"][number];
const PRICE_COLS: Column<PriceRow>[] = [
  { id: "product", header: "Produit", sortValue: (p) => p.productName, cell: (p) => <span className="font-medium">{p.productName}</span> },
  { id: "unit", header: "Unité", width: 80, muted: true, cell: (p) => UNIT_LABEL[p.unit as keyof typeof UNIT_LABEL] ?? p.unit },
  { id: "updated", header: "Mis à jour", width: 130, sortValue: (p) => p.updatedAt, cell: (p) => <DateLabel date={p.updatedAt} className="text-muted-foreground" /> },
  { id: "price", header: "Prix d'achat HT", width: 140, numeric: true, sortValue: (p) => p.price, cell: (p) => <Money value={p.price} className="font-medium" /> },
];
function PriceList({ prices }: { prices: PriceRow[] }) {
  const navigate = useNavigate();
  return (
    <Section title="Liste de prix" count={prices.length}>
      <DataTable inset pageKey="pricesPage" columns={PRICE_COLS} rows={prices} getRowId={(p) => p.productId} defaultSort={{ id: "product", dir: "asc" }}
        onRowClick={(p) => navigate(`/products/${p.productId}`)}
        empty={<EmptyFrame icon={Tag} text="Aucun prix référencé chez ce fournisseur." />} />
    </Section>
  );
}

const PO_COLS: Column<PurchaseOrderSummary>[] = [
  { id: "number", header: "N°", width: 170, sortKey: "number", cell: (p) => <Mono>{p.number}</Mono> },
  { id: "created", header: "Créée", width: 120, sortKey: "createdAt", cell: (p) => <DateLabel date={p.createdAt} className="text-muted-foreground" /> },
  { id: "expected", header: "Livraison prévue", sortKey: "date", cell: (p) => <DateLabel date={p.expectedDate} /> },
  { id: "lines", header: "Lignes", width: 70, numeric: true, muted: true, cell: (p) => p.lineCount },
  { id: "total", header: "Total HT", width: 110, numeric: true, sortKey: "total", cell: (p) => <Money value={p.totalHt} /> },
  { id: "status", header: "Statut", width: 160, sortKey: "status", cell: (p) => <StatusDot kind="purchaseOrder" value={p.status} /> },
];
/** Every purchase order of the supplier, newest first, one server page at a time. */
function PurchaseOrders({ supplierId, onOrder }: { supplierId: string; onOrder: () => void }) {
  const navigate = useNavigate();
  const list = useServerList({ pageKey: "ordersPage", sortKey: "ordersSort", defaultSort: { id: "createdAt", dir: "desc" } });
  const { data, isLoading } = usePurchaseOrdersPage({ supplierId, ...list.params });
  return (
    <Section title="Commandes d'achat" count={data?.total}>
      <DataTable inset server={{ list, total: data?.total }} columns={PO_COLS} rows={data?.items} loading={isLoading} getRowId={(p) => p.id}
        onRowClick={(p) => navigate(`/purchase-orders/${p.id}`)}
        empty={
          <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-border px-3 py-2 text-[12.5px] text-muted-foreground">
            <ShoppingBasket size={14} strokeWidth={1.75} />Aucune commande passée chez ce fournisseur.
            <Button size="sm" variant="ghost" icon={Plus} className="ml-auto" onClick={onOrder}>Commander</Button>
          </div>
        } />
    </Section>
  );
}

function Contacts({ contacts }: { contacts: SupplierDetail["contacts"] }) {
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

function EmptyFrame({ icon: Icon, text }: { icon: typeof Truck; text: string }) {
  return (
    <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-border px-3 py-3 text-[12.5px] text-muted-foreground">
      <Icon size={14} strokeWidth={1.75} />{text}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <Page>
      <PageHeader breadcrumb={[{ label: "Fournisseurs", to: "/suppliers" }]} title={<Skeleton className="h-4 w-48" />} />
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
