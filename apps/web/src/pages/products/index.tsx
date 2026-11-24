/** Produits — catalogue, server-paginated (useProductsPage): category tabs with counts, search (name / SKU / aliases), price,
 *  cost, margin, stock, next expiry; sort and page in the URL. */
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Package } from "lucide-react";
import type { ProductCategory, ProductSummary } from "@kit/shared";
import { categoryIds, categoryLabel, categoryOptions } from "@/lib/labels";
import { fmtPercent, UNIT_LABEL } from "@/lib/format";
import { useProductsPage, useTags } from "@/lib/queries";
import { TagList } from "@/ui/tags";
import { useDebounced, useUrlState } from "@/lib/url-state";
import { Button, DataTable, EmptyState, Money, Mono, Page, PageBody, PageHeader, Qty, SearchInput, Select, Tabs, useServerList, type Column } from "@/ui";
import { ExpiryLabel, useToday } from "@/pages/stock/shared";

const margin = (p: ProductSummary) => (p.price > 0 ? (p.price - p.cost) / p.price : 0);

function columns(today: string): Column<ProductSummary>[] {
  return [
    { id: "sku", header: "SKU", width: 130, sortKey: "sku", cell: (p) => <Mono>{p.sku}</Mono> },
    {
      id: "name", header: "Product", sortKey: "name",
      cell: (p) => {
        const sub = [p.caliber && !p.name.includes(p.caliber) ? p.caliber : null, p.origin].filter(Boolean).join(" · ");
        return (
          <span className="flex min-w-0 items-center gap-2">
            <span className={p.active ? "truncate font-medium" : "truncate font-medium text-muted-foreground line-through"}>{p.name}</span>
            {sub ? <span className="truncate text-[12px] text-muted-foreground">{sub}</span> : null}
          </span>
        );
      },
    },
    { id: "category", header: "Category", width: 140, hideBelow: 1100, muted: true, sortKey: "category", cell: (p) => categoryLabel(p.category) },
    { id: "tags", header: "Group", width: 160, hideBelow: 900, sortKey: "tags", cell: (p) => <TagList scope="product" tags={p.tags} max={2} fit empty={<span className="text-muted-foreground/60">—</span>} /> },
    { id: "unit", header: "Unit", width: 70, hideBelow: 1000, muted: true, cell: (p) => UNIT_LABEL[p.unit] ?? p.unit },
    { id: "price", header: "Price HT", width: 100, numeric: true, sortKey: "price", cell: (p) => <Money value={p.price} /> },
    { id: "cost", header: "Cost", width: 100, hideBelow: 1250, numeric: true, muted: true, sortKey: "cost", cell: (p) => <Money value={p.cost} tone="muted" /> },
    {
      id: "margin", header: "Margin", width: 80, numeric: true, sortKey: "margin",
      cell: (p) => {
        const m = margin(p);
        return <span className={m < 0.15 ? "text-warning" : "text-secondary-foreground"}>{fmtPercent(m)}</span>;
      },
    },
    {
      id: "available", header: "Available", width: 110, numeric: true, sortKey: "available",
      cell: (p) => <Qty value={p.available} unit={p.unit} tone={p.available <= 0 ? "destructive" : undefined} className="font-medium" />,
    },
    { id: "expiry", header: "Next DLC", width: 150, hideBelow: 1300, sortKey: "expiry", cell: (p) => <ExpiryLabel date={p.nextExpiry} today={today} /> },
  ];
}

export default function ProductsPage() {
  const navigate = useNavigate();
  const today = useToday();
  const [q, setQ] = useUrlState("q");
  const [category, setCategory] = useUrlState("category");
  const [tag, setTag] = useUrlState("tag");
  const dq = useDebounced(q, 200);
  const { data: tagDefs } = useTags("product");
  const tagOptions = useMemo(() => (tagDefs ?? []).map((t) => ({ value: t.id, label: `${t.label} (${t.count})` })), [tagDefs]);

  const list = useServerList({ defaultSort: { id: "name", dir: "asc" } });
  const { data: page, isLoading, isError, refetch } = useProductsPage({ q: dq, category: category as ProductCategory, tag, ...list.params });
  const data = page?.items;
  const total = page?.total ?? 0;
  // Tab counts per category (ignoring the category tab) come with the page.
  const counts = useMemo(() => {
    const m: Record<string, number> = { ...(page?.counts ?? {}) };
    m[""] = Object.values(page?.counts ?? {}).reduce((a, b) => a + b, 0);
    return m;
  }, [page?.counts]);
  const all = page;
  const cols = useMemo(() => columns(today), [today]);

  const tabs = [{ id: "", label: "All" }, ...categoryIds().filter((c) => !all || counts[c]).map((c) => ({ id: c as string, label: categoryLabel(c) }))];
  const filtered = !!(dq || category || tag);
  const reset = () => { setQ(""); setCategory(""); setTag(""); };

  return (
    <Page>
      <PageHeader
        title="Products"
        tabs={<Tabs value={category} onChange={setCategory} items={tabs.map((t) => ({ ...t, count: all ? counts[t.id] ?? 0 : undefined }))} />}
        filters={
          <>
            <SearchInput value={q} onChange={setQ} placeholder="Name, SKU Name..." />
            <Select size="sm" value={tag} onChange={setTag} placeholder="All groups" options={tagOptions} aria-label="Group" />
          </>
        }
      />
      <PageBody flush>
        {isError && !data ? (
          <EmptyState icon={Package} title="Catalogue not available" description="TheAPI Check that the server is running on port 4000." action={<Button size="sm" onClick={() => refetch()}>Retry</Button>} />
        ) : (
          <DataTable
            columns={cols}
            rows={data}
            server={{ list, total: page?.total }}
            loading={isLoading}
            getRowId={(p) => p.id}
            onRowClick={(p) => navigate(`/products/${p.id}`)}
            footer={data ? `${total} produit${total > 1 ? "s" : ""}${filtered ? " · filtered" : ""}` : undefined}
            empty={
              filtered ? (
                <EmptyState icon={Package} title="No products match" description="Try another name, one SKU or a name (&quot;wolf&quot;, &quot;daurad&quot;...)." action={<Button size="sm" onClick={reset}>Clear Filters</Button>} />
              ) : (
                <EmptyState icon={Package} title="No products" description="The catalog of the data pack will appear here." />
              )
            }
          />
        )}
      </PageBody>
    </Page>
  );
}
