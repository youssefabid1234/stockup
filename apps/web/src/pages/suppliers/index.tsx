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
  { id: "name", header: "Fournisseur", sortValue: (s) => s.name, cell: (s) => <span className="truncate font-medium">{s.name}</span> },
  { id: "city", header: "Ville", width: 150, muted: true, sortValue: (s) => s.city, cell: (s) => s.city || "—" },
  {
    id: "categories", header: "Catégories", width: 320, hideBelow: 1100,
    cell: (s) => (
      <span className="flex min-w-0 gap-1 overflow-hidden">
        {s.categories.map((c) => <Badge key={c}>{categoryLabel(c)}</Badge>)}
      </span>
    ),
  },
  { id: "tags", header: "Groupe", width: 170, sortValue: (s) => (s.tags ?? []).join(","), cell: (s) => <TagList scope="supplier" tags={s.tags} max={2} fit empty={<span className="text-muted-foreground/60">—</span>} /> },
  { id: "lead", header: "Délai", width: 80, numeric: true, sortValue: (s) => s.leadTimeDays, cell: (s) => `${s.leadTimeDays} j` },
  { id: "terms", header: "Paiement", width: 100, hideBelow: 1000, numeric: true, muted: true, sortValue: (s) => s.paymentTermsDays, cell: (s) => (s.paymentTermsDays ? `${s.paymentTermsDays} j` : "Comptant") },
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
        title="Fournisseurs"
        count={all?.length}
        filters={
          <>
            <SearchInput value={q} onChange={setQ} placeholder="Nom, ville, contact…" />
            <Select size="sm" value={category} onChange={setCategory} placeholder="Toutes les catégories" options={categoryOptions()} />
            <Select size="sm" value={tag} onChange={setTag} placeholder="Tous les groupes" options={tagOptions} aria-label="Groupe" />
          </>
        }
      />
      <PageBody flush>
        {isError && !data ? (
          <EmptyState icon={Truck} title="Fournisseurs indisponibles" description="L'API ne répond pas. Vérifiez que le serveur tourne sur le port 4000." action={<Button size="sm" onClick={() => refetch()}>Réessayer</Button>} />
        ) : (
          <DataTable
            columns={COLUMNS}
            rows={rows}
            loading={isLoading}
            getRowId={(s) => s.id}
            onRowClick={(s) => navigate(`/suppliers/${s.id}`)}
            defaultSort={{ id: "name", dir: "asc" }}
            footer={rows ? `${rows.length} fournisseur${rows.length > 1 ? "s" : ""}${filtered ? " · filtrés" : ""}` : undefined}
            empty={
              filtered ? (
                <EmptyState icon={Truck} title="Aucun fournisseur ne correspond" description="Modifiez la recherche ou la catégorie." action={<Button size="sm" onClick={() => { setQ(""); setCategory(""); setTag(""); }}>Effacer les filtres</Button>} />
              ) : (
                <EmptyState icon={Truck} title="Aucun fournisseur" description="Les fournisseurs du data pack apparaîtront ici." />
              )
            }
          />
        )}
      </PageBody>
    </Page>
  );
}
