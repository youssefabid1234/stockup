/** Stocks — every StockLevel, server-paginated (useStockPage): Tout / Rupture / Stock bas / DLC proche tabs with counts
 *  (filtered by the API), search, sort; row → side panel with lots + adjust. */
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowUpRight, Boxes, SlidersHorizontal } from "lucide-react";
import type { Product, StockLevel } from "@kit/shared";
import { categoryIds, categoryLabel, categoryOptions } from "@/lib/labels";
import { useDashboard, useStockPage } from "@/lib/queries";
import { useDebounced, useUrlState } from "@/lib/url-state";
import {
  Button, DataTable, EmptyState, KeyValue, Mono, Page, PageBody, PageHeader, Qty, SearchInput, Section, SidePanel, StatusDot,
  Tabs, useServerList, type Column,
} from "@/ui";
import { AdjustStockPanel, ExpiryLabel, fefo, LotsTable, stockTone, useToday } from "./shared";

type Row = StockLevel & { product: Product };
const TABS = [
  { id: "", label: "Tout" },
  { id: "out", label: "Rupture" },
  { id: "low", label: "Stock bas" },
  { id: "expiring", label: "DLC proche" },
] as const;
type Tab = (typeof TABS)[number]["id"];


export default function StockPage() {
  const today = useToday();
  const [tab, setTab] = useUrlState("tab");
  const [q, setQ] = useUrlState("q");
  const [sel, setSel] = useUrlState("p", "", { keepPage: true });
  const dq = useDebounced(q, 150);
  const list = useServerList({ defaultSort: { id: "product", dir: "asc" } });
  const { data: page, isLoading, isError, refetch } = useStockPage({ q: dq || undefined, tab: tab as Tab, ...list.params });
  const { data: dash } = useDashboard();
  const data = page?.items;
  const rows = data;
  const total = page?.total ?? 0;

  // Row tone: rupture = available ≤ 0; "Stock bas" = the API's rule (dashboard: < 2 days of average sales).
  const lowIds = useMemo(() => new Set((dash?.lowStock ?? []).map((l) => l.productId)), [dash]);
  const is = useMemo(() => ({
    out: (r: Row) => r.available <= 0,
    low: (r: Row) => r.available > 0 && (tab === "low" || lowIds.has(r.productId)),
  }), [lowIds, tab]);
  // Tab counts (ignoring the tab) are computed by the API over the search.
  const counts = (page?.counts ?? {}) as Partial<Record<Tab, number>>;

  const columns = useMemo<Column<Row>[]>(() => [
    {
      id: "product", header: "Produit", sortKey: "product",
      cell: (r) => (
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate font-medium">{r.product.name}</span>
          <Mono className="text-muted-foreground">{r.product.sku}</Mono>
        </span>
      ),
    },
    { id: "category", header: "Catégorie", width: 140, hideBelow: 1100, muted: true, sortKey: "category", cell: (r) => categoryLabel(r.product.category) },
    { id: "onHand", header: "En stock", width: 110, numeric: true, sortKey: "onHand", cell: (r) => <Qty value={r.onHand} unit={r.product.unit} /> },
    { id: "reserved", header: "Réservé", width: 100, hideBelow: 1000, numeric: true, sortKey: "reserved", cell: (r) => <Qty value={r.reserved} unit={r.product.unit} className={r.reserved ? undefined : "text-muted-foreground"} /> },
    {
      id: "available", header: "Disponible", width: 110, numeric: true, sortKey: "available",
      cell: (r) => <Qty value={r.available} unit={r.product.unit} tone={r.available <= 0 ? "destructive" : is.low(r) ? "warning" : undefined} className="font-medium" />,
    },
    { id: "incoming", header: "Entrant", width: 100, hideBelow: 1000, numeric: true, sortKey: "incoming", cell: (r) => <Qty value={r.incoming} unit={r.product.unit} className={r.incoming ? "text-info" : "text-muted-foreground"} /> },
    { id: "expiry", header: "Prochaine DLC", width: 150, sortKey: "expiry", cell: (r) => <ExpiryLabel date={r.nextExpiry} today={today} /> },
    {
      id: "state", header: "État", width: 110, sortKey: "state",
      cell: (r) => { const s = stockTone(r.available, is.low(r)); return <StatusDot tone={s.tone} label={s.label} />; },
    },
  ], [today, is]);

  const selected = sel ? data?.find((r) => r.productId === sel) : undefined;
  const filtered = !!(tab || dq);

  return (
    <Page>
      <PageHeader
        title="Stocks"
        tabs={<Tabs<Tab> value={tab as Tab} onChange={setTab} items={TABS.map((t) => ({ ...t, count: page ? counts[t.id] ?? 0 : undefined }))} />}
        filters={<SearchInput value={q} onChange={setQ} placeholder="Produit, SKU…" />}
      />
      <PageBody flush>
        {isError && !data ? (
          <EmptyState icon={Boxes} title="Stocks indisponibles" description="L'API ne répond pas. Vérifiez que le serveur tourne sur le port 4000." action={<Button size="sm" onClick={() => refetch()}>Réessayer</Button>} />
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            server={{ list, total: page?.total }}
            loading={isLoading}
            getRowId={(r) => r.productId}
            selectedId={sel || null}
            onRowClick={(r) => setSel(r.productId === sel ? "" : r.productId)}
            footer={rows ? `${total} produit${total > 1 ? "s" : ""}${filtered ? " · filtrés" : ""}` : undefined}
            empty={
              <EmptyState
                icon={Boxes}
                title={tab === "out" ? "Aucune rupture" : tab === "low" ? "Aucun stock bas" : tab === "expiring" ? "Aucune DLC proche" : "Aucun produit ne correspond"}
                description={tab ? "Rien à signaler dans cette vue." : "Modifiez la recherche."}
                action={filtered ? <Button size="sm" onClick={() => { setTab(""); setQ(""); }}>Tout afficher</Button> : undefined}
              />
            }
          />
        )}
      </PageBody>
      {selected ? <StockPanel row={selected} low={is.low(selected)} today={today} onClose={() => setSel("")} /> : null}
    </Page>
  );
}

function StockPanel({ row, low, today, onClose }: { row: Row; low: boolean; today: string; onClose: () => void }) {
  const navigate = useNavigate();
  const [adjusting, setAdjusting] = useState(false);
  const p = row.product;
  const s = stockTone(row.available, low);
  if (adjusting) {
    return <AdjustStockPanel productId={p.id} productName={p.name} unit={p.unit} available={row.available} onClose={() => setAdjusting(false)} />;
  }
  return (
    <SidePanel
      title={p.name}
      subtitle={<span className="font-mono">{p.sku}</span>}
      onClose={onClose}
      actions={<Button size="sm" variant="ghost" iconRight={ArrowUpRight} onClick={() => navigate(`/products/${p.id}`)}>Fiche</Button>}
      footer={<Button variant="primary" icon={SlidersHorizontal} onClick={() => setAdjusting(true)}>Ajuster le stock</Button>}
    >
      <div className="flex flex-col gap-6">
        <Section title="Niveaux">
          <KeyValue
            labelWidth={130}
            items={[
              { label: "État", value: <StatusDot tone={s.tone} label={s.label} /> },
              { label: "En stock", value: <Qty value={row.onHand} unit={p.unit} /> },
              { label: "Réservé", value: <Qty value={row.reserved} unit={p.unit} /> },
              { label: "Disponible", value: <Qty value={row.available} unit={p.unit} tone={row.available <= 0 ? "destructive" : undefined} className="font-medium" /> },
              { label: "Entrant", value: <Qty value={row.incoming} unit={p.unit} /> },
              { label: "Prochaine DLC", value: <ExpiryLabel date={row.nextExpiry} today={today} /> },
            ]}
          />
        </Section>
        <Section title="Lots · FEFO" count={fefo(row.lots).length}>
          <LotsTable compact lots={row.lots} unit={p.unit} today={today}
            empty={<div className="rounded-[6px] border border-dashed border-border px-3 py-3 text-[12.5px] text-muted-foreground">Aucun lot en stock.</div>} />
        </Section>
      </div>
    </SidePanel>
  );
}
