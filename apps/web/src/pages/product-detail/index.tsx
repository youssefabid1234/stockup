/** Produit — KPIs, lots (FEFO), supplier prices compared, recent movements, "Ajuster le stock" side panel. */
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeftRight, Boxes, Package, SlidersHorizontal, Truck } from "lucide-react";
import type { ProductDetail, StockMovement } from "@kit/shared";
import { categoryIds, categoryLabel, categoryOptions, MOVEMENT_REASON_LABEL } from "@/lib/labels";
import { fmtPercent, fmtQty, UNIT_LABEL } from "@/lib/format";
import { useProduct, useStockMovements, useSuppliers } from "@/lib/queries";
import { EntityContext } from "@/pages/context/shared";
import {
  Badge, Button, DataTable, DateLabel, EmptyState, KeyValue, Money, Mono, Page, PageBody, PageHeader, Qty, Section, Skeleton,
  Stat, StatGrid, useServerList, type Column,
} from "@/ui";
import { TagEditor } from "@/ui/tags";
import { GroupsStrip } from "@/pages/history/timeline";
import { AdjustStockPanel, ExpiryLabel, fefo, LotsTable, useToday } from "@/pages/stock/shared";

export default function ProductDetailPage() {
  const { id = "" } = useParams();
  const { data: p, isLoading, isError } = useProduct(id);

  if (isLoading) return <DetailSkeleton />;
  if (isError || !p) {
    return (
      <Page>
        <PageHeader breadcrumb={[{ label: "Produits", to: "/products" }]} title={id} />
        <PageBody><EmptyState icon={Package} title="Produit introuvable" description={`Aucun produit ne correspond à l'identifiant ${id}.`} /></PageBody>
      </Page>
    );
  }
  return <ProductView p={p} />;
}

function ProductView({ p }: { p: ProductDetail }) {
  const today = useToday();
  const [adjusting, setAdjusting] = useState(false);
  const { data: suppliers } = useSuppliers();
  const supplierName = useMemo(() => {
    const m = new Map((suppliers ?? []).map((s) => [s.id, s.name]));
    return (sid?: string) => (sid ? m.get(sid) : undefined);
  }, [suppliers]);
  const lots = fefo(p.stock.lots);
  const margin = p.price > 0 ? (p.price - p.cost) / p.price : 0;

  return (
    <Page>
      <PageHeader
        breadcrumb={[{ label: "Produits", to: "/products" }]}
        title={p.name}
        meta={
          <>
            <Mono className="text-muted-foreground">{p.sku}</Mono>
            <Badge>{categoryLabel(p.category)}</Badge>
            {!p.active ? <Badge tone="destructive">Inactif</Badge> : null}
          </>
        }
        actions={<Button variant="primary" icon={SlidersHorizontal} onClick={() => setAdjusting(true)}>Ajuster le stock</Button>}
      />
      <PageBody flush>
        <GroupsStrip><TagEditor scope="product" value={p.tags} entityId={p.id} /></GroupsStrip>
        <StatGrid className="md:grid-cols-5">
          <Stat label="Disponible" value={<Qty value={p.stock.available} unit={p.unit} />} tone={p.stock.available <= 0 ? "destructive" : undefined}
            hint={p.stock.available <= 0 ? "Rupture" : "En stock − réservé"} />
          <Stat label="En stock" value={<Qty value={p.stock.onHand} unit={p.unit} />} hint={`${lots.length} lot${lots.length > 1 ? "s" : ""}`} />
          <Stat label="Réservé" value={<Qty value={p.stock.reserved} unit={p.unit} />} hint="Commandes confirmées" />
          <Stat label="Entrant" value={<Qty value={p.stock.incoming} unit={p.unit} />} tone={p.stock.incoming > 0 ? "info" : undefined} hint="Achats en cours" />
          <Stat label="Ventes 30 j" value={<Qty value={p.sales30d.qty} unit={p.unit} />} hint={<Money value={p.sales30d.revenue} compact />} />
        </StatGrid>

        <div className="grid grid-cols-1 gap-8 px-5 py-5 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex min-w-0 flex-col gap-7">
            <Section title="Lots en stock · FEFO" count={lots.length}
              actions={p.stock.nextExpiry ? <span className="text-[12px] text-muted-foreground">Prochaine DLC <ExpiryLabel date={p.stock.nextExpiry} today={today} /></span> : null}>
              <LotsTable lots={p.stock.lots} unit={p.unit} today={today} supplierName={supplierName}
                empty={<EmptyFrame icon={Boxes} text="Aucun lot en stock pour ce produit." />} />
            </Section>
            <SupplierPrices p={p} />
            <EntityContext scope="product" id={p.id} label={p.name} />
            <Movements p={p} />
          </div>
          <aside className="flex min-w-0 flex-col gap-7">
            <Section title="Appellations" count={p.aliases.length}>
              {p.aliases.length ? (
                <div className="flex flex-wrap gap-1.5">{p.aliases.map((a) => <Badge key={a} tone="violet">{a}</Badge>)}</div>
              ) : (
                <div className="text-[12.5px] text-muted-foreground">Aucune appellation. L'agent vocal ne reconnaît que le nom exact.</div>
              )}
            </Section>
            <Section title="Informations">
              <KeyValue
                labelWidth={120}
                items={[
                  { label: "SKU", value: p.sku, mono: true },
                  { label: "Catégorie", value: categoryLabel(p.category) },
                  { label: "Unité", value: UNIT_LABEL[p.unit] ?? p.unit },
                  { label: "Calibre", value: p.caliber || "—" },
                  { label: "Origine", value: p.origin || "—" },
                  { label: "Prix catalogue", value: <Money value={p.price} /> },
                  { label: "Coût de référence", value: <Money value={p.cost} /> },
                  { label: "Marge", value: <span className={margin < 0.15 ? "text-warning" : undefined}>{fmtPercent(margin)}</span> },
                  { label: "TVA", value: `${(Math.round(p.vatRate * 1000) / 10).toLocaleString("fr-FR")} %` },
                  { label: "Conservation", value: `${p.shelfLifeDays} jour${p.shelfLifeDays > 1 ? "s" : ""}` },
                  { label: "Fournisseur principal", value: p.mainSupplierId ? <Link className="hover:underline" to={`/suppliers/${p.mainSupplierId}`}>{supplierName(p.mainSupplierId) ?? p.mainSupplierId}</Link> : "—" },
                ]}
              />
            </Section>
          </aside>
        </div>
      </PageBody>
      {adjusting ? (
        <AdjustStockPanel productId={p.id} productName={p.name} unit={p.unit} available={p.stock.available} onClose={() => setAdjusting(false)} />
      ) : null}
    </Page>
  );
}

type SupplierPriceRow = ProductDetail["supplierPrices"][number];
function SupplierPrices({ p }: { p: ProductDetail }) {
  const navigate = useNavigate();
  const best = p.supplierPrices.length ? Math.min(...p.supplierPrices.map((s) => s.price)) : undefined;
  const cols: Column<SupplierPriceRow>[] = [
    {
      id: "supplier", header: "Fournisseur", sortValue: (s) => s.supplierName,
      cell: (s) => (
        <span className="flex items-center gap-2">
          <span className={s.price === best ? "font-medium" : undefined}>{s.supplierName}</span>
          {s.supplierId === p.mainSupplierId ? <span className="text-[12px] text-muted-foreground">· principal</span> : null}
          {s.price === best && p.supplierPrices.length > 1 ? <Badge tone="success">Meilleur prix</Badge> : null}
        </span>
      ),
    },
    { id: "updated", header: "Mis à jour", width: 120, sortValue: (s) => s.updatedAt, cell: (s) => <DateLabel date={s.updatedAt} className="text-muted-foreground" /> },
    {
      id: "delta", header: "Écart", width: 90, numeric: true, sortValue: (s) => s.price - (best ?? 0),
      cell: (s) => (best === undefined || s.price === best ? <span className="text-muted-foreground">—</span> : <span className="text-muted-foreground">+{fmtPercent((s.price - best) / best)}</span>),
    },
    {
      id: "margin", header: "Marge à ce prix", width: 120, numeric: true, sortValue: (s) => p.price - s.price,
      cell: (s) => <span className="text-secondary-foreground">{p.price > 0 ? fmtPercent((p.price - s.price) / p.price) : "—"}</span>,
    },
    {
      id: "price", header: `Prix d'achat / ${UNIT_LABEL[p.unit] ?? p.unit}`, width: 150, numeric: true, sortValue: (s) => s.price,
      cell: (s) => <Money value={s.price} tone={s.price === best ? "success" : undefined} className="font-medium" />,
    },
  ];
  return (
    <Section title="Prix fournisseurs" count={p.supplierPrices.length}>
      <DataTable inset paginate={false} columns={cols} rows={p.supplierPrices} getRowId={(s) => s.supplierId} defaultSort={{ id: "price", dir: "asc" }}
        onRowClick={(s) => navigate(`/suppliers/${s.supplierId}`)}
        empty={<EmptyFrame icon={Truck} text="Aucun fournisseur référencé pour ce produit." />} />
    </Section>
  );
}

function Movements({ p }: { p: ProductDetail }) {
  const navigate = useNavigate();
  // Full history, one server page at a time (newest first; click "Date" for oldest first). The detail's last 30 show
  // while the first page loads.
  const list = useServerList({ pageKey: "movesPage", sortKey: "movesSort", defaultSort: { id: "at", dir: "desc" } });
  const { data: history } = useStockMovements({ productId: p.id, ...list.params });
  const rows = history?.items ?? p.movements;
  const cols: Column<StockMovement>[] = [
    { id: "at", header: "Date", width: 170, sortKey: "at", cell: (m) => <DateLabel date={m.at} format="datetime" className="text-secondary-foreground" /> },
    {
      id: "reason", header: "Mouvement", width: 120,
      cell: (m) => <span className={m.reason === "waste" ? "text-destructive" : undefined}>{MOVEMENT_REASON_LABEL[m.reason] ?? m.reason}</span>,
    },
    {
      id: "ref", header: "Référence",
      cell: (m) => (
        <span className="flex min-w-0 items-center gap-2">
          {m.refType === "manual" ? <span className="text-muted-foreground">Manuel</span> : m.refId ? <Mono>{m.refId}</Mono> : <span className="text-muted-foreground">—</span>}
          {m.note ? <span className="truncate text-[12px] text-muted-foreground">{m.note}</span> : null}
        </span>
      ),
    },
    { id: "lot", header: "Lot", width: 120, cell: (m) => (m.lotId ? <Mono className="text-muted-foreground">{m.lotId}</Mono> : null) },
    {
      id: "qty", header: "Quantité", width: 110, numeric: true,
      cell: (m) => <span className={m.qty > 0 ? "num text-success" : "num text-secondary-foreground"}>{m.qty > 0 ? "+" : "−"}{fmtQty(Math.abs(m.qty), p.unit)}</span>,
    },
  ];
  const go = (m: StockMovement) => {
    if (m.refType === "order" && m.refId) navigate(`/orders/${m.refId}`);
    else if (m.refType === "purchase_order" && m.refId) navigate(`/purchase-orders/${m.refId}`);
  };
  return (
    <Section title="Mouvements" count={history?.total}>
      <DataTable inset server={{ list, total: history?.total }} columns={cols} rows={rows} getRowId={(m) => m.id} onRowClick={go}
        empty={<EmptyFrame icon={ArrowLeftRight} text="Aucun mouvement de stock récent." />} />
    </Section>
  );
}

function EmptyFrame({ icon: Icon, text }: { icon: typeof Package; text: string }) {
  return (
    <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-border px-3 py-3 text-[12.5px] text-muted-foreground">
      <Icon size={14} strokeWidth={1.75} />{text}
    </div>
  );
}

function DetailSkeleton() {
  return (
    <Page>
      <PageHeader breadcrumb={[{ label: "Produits", to: "/products" }]} title={<Skeleton className="h-4 w-48" />} />
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
