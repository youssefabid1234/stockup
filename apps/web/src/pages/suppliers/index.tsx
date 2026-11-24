/** Fournisseurs — list (useSuppliers): name, city, categories, lead time, terms, min order. Search + category filter in the URL. */
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { Truck } from "lucide-react";
import type { ProductCategory, Supplier } from "@kit/shared";
import { categoryIds, categoryLabel, categoryOptions } from "@/lib/labels";
import { useSuppliers, useTags } from "@/lib/queries";
import { TagList } from "@/ui/tags";
import { useDebounced, useUrlState } from "@/lib/url-state";
import { Badge, Button, DataTable, EmptyState, Money, Page, PageBody, PageHeader, SearchInput, Select, type Column } from "@/ui";

const norm = (s: string) => s.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();

const COLUMNS: Column<Supplier>[] = [
  { id: "name", header: "Supplier", sortValue: (s) => s.name, cell: (s) => <span className="truncate font-medium">{s.name}</span> },
  { id: "city", header: "City", width: 150, muted: true, sortValue: (s) => s.city, cell: (s) => s.city || "—" },
  {
    id: "categories", header: "Categories", width: 320, hideBelow: 1100,
    cell: (s) => (
      <span className="flex min-w-0 gap-1 overflow-hidden">
        {s.categories.map((c) => <Badge key={c}>{categoryLabel(c)}</Badge>)}
      </span>
    ),
  },
  { id: "tags", header: "Group", width: 170, sortValue: (s) => (s.tags ?? []).join(","), cell: (s) => <TagList scope="supplier" tags={s.tags} max={2} fit empty={<span className="text-muted-foreground/60">—</span>} /> },
  { id: "lead", header: "Delay", width: 80, numeric: true, sortValue: (s) => s.leadTimeDays, cell: (s) => `${s.leadTimeDays} j` },
  { id: "terms", header: "Payment", width: 100, hideBelow: 1000, numeric: true, muted: true, sortValue: (s) => s.paymentTermsDays, cell: (s) => (s.paymentTermsDays ? `${s.paymentTermsDays} j` : "Cash") },
  { id: "min", header: "Minimum", width: 110, numeric: true, sortValue: (s) => s.minOrderAmount, cell: (s) => <Money value={s.minOrderAmount} compact zeroMuted /> },
];

export default function SuppliersPage() {
  const navigate = useNavigate();
  const [q, setQ] = useUrlState("q");
  const [category, setCategory] = useUrlState("category");
  const [tag, setTag] = useUrlState("tag");
  const dq = useDebounced(q, 150);
  const { data, isLoading, isError, refetch } = useSuppliers({ tag });
  const { data: all } = useSuppliers();
  const { data: tagDefs } = useTags("supplier");
  const tagOptions = useMemo(() => (tagDefs ?? []).map((t) => ({ value: t.id, label: `${t.label} (${t.count})` })), [tagDefs]);

  const rows = useMemo(() => {
    if (!data) return data;
    const n = norm(dq);
    return data.filter((s) =>
      (!category || s.categories.includes(category as ProductCategory)) &&
      (!n || norm(`${s.name} ${s.city} ${s.contacts.map((c) => c.name).join(" ")}`).includes(n)));
  }, [data, dq, category]);
  const filtered = !!(dq || category || tag);

  return (
    <Page>
      <PageHeader
        title="Suppliers"
        count={all?.length}
        filters={
          <>
            <SearchInput value={q} onChange={setQ} placeholder="Name, city, contact..." />
            <Select size="sm" value={category} onChange={setCategory} placeholder="All categories" options={categoryOptions()} />
            <Select size="sm" value={tag} onChange={setTag} placeholder="All groups" options={tagOptions} aria-label="Group" />
          </>
        }
      />
      <PageBody flush>
        {isError && !data ? (
          <EmptyState icon={Truck} title="Suppliers not available" description="TheAPI Check that the server is running on port 4000." action={<Button size="sm" onClick={() => refetch()}>Retry</Button>} />
        ) : (
          <DataTable
            columns={COLUMNS}
            rows={rows}
            loading={isLoading}
            getRowId={(s) => s.id}
            onRowClick={(s) => navigate(`/suppliers/${s.id}`)}
            defaultSort={{ id: "name", dir: "asc" }}
            footer={rows ? `${rows.length} fournisseur${rows.length > 1 ? "s" : ""}${filtered ? " · filtered" : ""}` : undefined}
            empty={
              filtered ? (
                <EmptyState icon={Truck} title="No supplier matches" description="Change the search or category." action={<Button size="sm" onClick={() => { setQ(""); setCategory(""); setTag(""); }}>Clear Filters</Button>} />
              ) : (
                <EmptyState icon={Truck} title="No supplier" description="The data pack providers will appear here." />
              )
            }
          />
        )}
      </PageBody>
    </Page>
  );
}
