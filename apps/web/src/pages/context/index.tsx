/**
 * Contexte — the context table: every fact the agents can read (company rules, clients, suppliers, products, rayons).
 * Tabs = scope; filters (search, genre, source, entity) in the URL, server-side; DataTable (100/page); row click opens
 * the side panel (autosaved edit); "Nouvelle fiche" creates one. AI / voice entries are tinted violet.
 * Live: context.* activity events refresh qk.context.
 */
import { useMemo } from "react";
import { BookOpen, Plus, X } from "lucide-react";
import type { ContextEntrySummary, ContextKind, ContextScope } from "@kit/shared";
import { useContextEntry, useContextPage } from "@/lib/queries";
import { useDebounced, useUrlState } from "@/lib/url-state";
import { cn } from "@/lib/cn";
import { Button, DataTable, DateLabel, EmptyState, Page, PageBody, PageHeader, SearchInput, Select, Tabs, useServerList, type Column } from "@/ui";
import {
  CONTEXT_SCOPE_LABEL, ContextPanel, KIND_OPTIONS, KindDot, NewContextPanel, SOURCE_OPTIONS, SourceMark, isAiSource,
} from "./shared";

const SCOPE_TABS: { id: "" | ContextScope; label: string }[] = [
  { id: "", label: "Toutes" },
  { id: "company", label: "Entreprise" },
  { id: "client", label: "Clients" },
  { id: "supplier", label: "Fournisseurs" },
  { id: "product", label: "Produits" },
  { id: "category", label: "Rayons" },
];

/** First meaningful line of the body, without markdown marks. */
const preview = (body: string) =>
  (body.split("\n").find((l) => l.trim() && !l.trim().startsWith("|")) ?? "").replace(/^\s*[-*]\s+/, "").replace(/\*\*|`/g, "").replace(/(?<![\w])_([^_]+)_(?![\w])/g, "$1");

const COLUMNS: Column<ContextEntrySummary>[] = [
  {
    id: "title", header: "Fiche", sortKey: "title", className: "w-full max-w-0", // fill, and let the preview truncate
    cell: (e) => (
      <span className="flex min-w-0 items-center gap-2">
        {isAiSource(e.source) ? <SourceMark source={e.source} compact /> : null}
        <span className={cn("shrink-0 truncate font-medium", isAiSource(e.source) && "text-violet")} style={{ maxWidth: "60%" }}>{e.title}</span>
        <span className="truncate text-muted-foreground">{preview(e.body)}</span>
      </span>
    ),
  },
  {
    id: "entity", header: "Concerne", width: 230, sortKey: "entity",
    cell: (e) => (
      <span className="flex min-w-0 items-baseline gap-1.5">
        <span className="truncate">{e.entityLabel}</span>
        {e.entityType !== "company" ? <span className="shrink-0 text-[11.5px] text-muted-foreground">{CONTEXT_SCOPE_LABEL[e.entityType]}</span> : null}
      </span>
    ),
  },
  { id: "kind", header: "Genre", width: 120, sortKey: "kind", cell: (e) => <KindDot kind={e.kind} /> },
  { id: "tags", header: "Mots-clés", width: 170, hideBelow: 1400, muted: true, sortKey: "tags", cell: (e) => <span className="truncate">{(e.tags ?? []).join(", ") || "—"}</span> },
  { id: "source", header: "Source", width: 130, hideBelow: 1200, sortKey: "source", cell: (e) => <SourceMark source={e.source} /> },
  { id: "updated", header: "Modifiée", width: 110, hideBelow: 1100, sortKey: "updated", cell: (e) => <DateLabel date={e.updatedAt} className="text-secondary-foreground" /> },
];

export default function ContextPage() {
  const [scope, setScope] = useUrlState("scope");
  const [kind, setKind] = useUrlState("kind");
  const [source, setSource] = useUrlState("source");
  const [entity, setEntity] = useUrlState("entity");
  const [q, setQ] = useUrlState("q");
  const [sel, setSel] = useUrlState("e", "", { keepPage: true });
  const [creating, setCreating] = useUrlState("new", "", { keepPage: true });
  const dq = useDebounced(q, 250);

  const params = { entityType: scope || undefined, kind: kind || undefined, source: source || undefined, entityId: entity || undefined, q: dq || undefined };
  // Default order = relevance with a search, else by entity (API); a column click sorts server-side.
  const list = useServerList({ defaultSort: { id: "relevance", dir: "asc" } });
  const { data: page, isLoading, isError, refetch } = useContextPage({ ...params, ...list.params });
  const data = page?.items;
  // Tab counts per entity type (ignoring the tab) and the agents' share come with the page.
  const counts = useMemo(() => {
    const m: Record<string, number> = { ...(page?.counts ?? {}) };
    m[""] = Object.values(page?.counts ?? {}).reduce((a, b) => a + b, 0);
    return m;
  }, [page?.counts]);
  const all = page;
  const aiCount = (page?.countsBySource?.ai_chat ?? 0) + (page?.countsBySource?.voice_agent ?? 0);
  const entityRow = entity ? data?.find((e) => e.entityId === entity) : undefined;
  const entityLabel = entityRow?.entityLabel ?? entity;

  const inList = data?.find((e) => e.id === sel);
  const { data: fetched } = useContextEntry(sel && !inList ? sel : undefined);
  const selected = inList ?? fetched;

  const filtered = !!(scope || kind || source || entity || dq);
  const reset = () => { setScope(""); setKind(""); setSource(""); setEntity(""); setQ(""); };
  const total = page?.total ?? 0;

  return (
    <Page>
      <PageHeader
        title="Contexte"
        tabs={
          <Tabs<"" | ContextScope>
            value={scope as "" | ContextScope}
            onChange={setScope}
            items={SCOPE_TABS.map((t) => ({ ...t, count: all ? counts[t.id] ?? 0 : undefined }))}
          />
        }
        filters={
          <>
            <SearchInput value={q} onChange={setQ} placeholder="Chercher dans les fiches…" className="w-[260px]" />
            <Select size="sm" value={kind} onChange={setKind} placeholder="Tous les genres" options={KIND_OPTIONS} aria-label="Genre" />
            <Select size="sm" value={source} onChange={setSource} placeholder="Toutes les sources" options={SOURCE_OPTIONS} aria-label="Source" />
            {entity ? (
              <Button size="sm" variant="ghost" icon={X} onClick={() => setEntity("")} title="Retirer ce filtre">
                {entityLabel}
              </Button>
            ) : null}
            {filtered ? <Button size="sm" variant="ghost" className="ml-auto" onClick={reset}>Effacer les filtres</Button> : null}
          </>
        }
        actions={<Button variant="primary" icon={Plus} onClick={() => setCreating("1")}>Nouvelle fiche</Button>}
      />
      <PageBody flush>
        {isError && !data ? (
          <EmptyState icon={BookOpen} title="Contexte indisponible" description="L'API ne répond pas. Vérifiez que le serveur tourne sur le port 4000." action={<Button size="sm" onClick={() => refetch()}>Réessayer</Button>} />
        ) : (
          <DataTable
            columns={COLUMNS}
            rows={data}
            server={{ list, total: page?.total }}
            loading={isLoading}
            getRowId={(e) => e.id}
            onRowClick={(e) => setSel(sel === e.id ? "" : e.id)}
            selectedId={sel || null}
            footer={data ? `${total} fiche${total > 1 ? "s" : ""}${filtered ? " · filtrées" : ""}${dq ? " · triées par pertinence" : ""}${aiCount ? ` · ${aiCount} écrite${aiCount > 1 ? "s" : ""} par les agents` : ""}` : undefined}
            empty={
              filtered ? (
                <EmptyState icon={BookOpen} title="Aucune fiche ne correspond" description="Modifiez la recherche ou les filtres." action={<Button size="sm" onClick={reset}>Effacer les filtres</Button>} />
              ) : (
                <EmptyState icon={BookOpen} title="Aucune fiche de contexte" description="Les fiches du data pack et celles écrites par les agents apparaîtront ici." action={<Button size="sm" icon={Plus} onClick={() => setCreating("1")}>Nouvelle fiche</Button>} />
              )
            }
          />
        )}
      </PageBody>
      {selected && !creating ? <ContextPanel key={selected.id} entry={selected} onClose={() => setSel("")} /> : null}
      {creating ? (
        <NewContextPanel
          defaults={{ scope: (entityRow?.entityType ?? (scope || "company")) as ContextScope, entityId: entity || undefined, kind: (kind || undefined) as ContextKind | undefined }}
          onClose={() => setCreating("")}
          onCreated={(e) => setSel(e.id)}
        />
      ) : null}
    </Page>
  );
}
