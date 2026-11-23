/**
 * Clients — REFERENCE LIST PAGE. Copy this pattern for every list:
 *  - filters live in the URL (useUrlState) and are passed to the query hook,
 *  - server-side pagination: useServerList (page + sort in the URL) → use…Page hook (ONE page of 100 + total + extras),
 *    <DataTable server={{ list, total }}> with `sortKey` columns; tab counts / filter options / footer come from the Page,
 *  - one PageHeader row: title + count · tabs · filters ……… primary action,
 *  - <PageBody flush> + <DataTable> (sticky header, 34px rows, numeric right-aligned, live flash),
 *  - row click → detail page, realistic empty/loading states,
 *  - create flow in a <SidePanel> (no modal).
 */
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Users } from "lucide-react";
import type { ClientSummary, ClientType } from "@kit/shared";
import { api } from "@/lib/api";
import { CLIENT_TYPE_LABEL } from "@/lib/labels";
import { qk, useApiMutation, useClientsPage, useTags } from "@/lib/queries";
import { TagList } from "@/ui/tags";
import { useDebounced, useUrlState } from "@/lib/url-state";
import {
  Button, DataTable, DateLabel, EmptyState, Field, Input, Money, Mono, Page, PageBody, PageHeader, SearchInput, Select,
  SidePanel, StatusDot, Tabs, useServerList, type Column,
} from "@/ui";

const STATUS_TABS = [
  { id: "", label: "Tous" },
  { id: "active", label: "Actifs" },
  { id: "blocked", label: "Bloqués" },
  { id: "prospect", label: "Prospects" },
] as const;
type StatusTab = (typeof STATUS_TABS)[number]["id"];

const TYPE_OPTIONS = Object.entries(CLIENT_TYPE_LABEL).map(([value, label]) => ({ value, label }));

const COLUMNS: Column<ClientSummary>[] = [
  {
    id: "name", header: "Client", sortKey: "name",
    cell: (c) => (
      <span className="flex min-w-0 items-center gap-2">
        <span className="truncate font-medium">{c.name}</span>
        <Mono className="text-muted-foreground">{c.code}</Mono>
      </span>
    ),
  },
  { id: "type", header: "Type", width: 170, hideBelow: 1300, muted: true, sortKey: "type", cell: (c) => CLIENT_TYPE_LABEL[c.type] ?? c.type },
  { id: "tags", header: "Groupe", width: 170, sortKey: "tags", cell: (c) => <TagList scope="client" tags={c.tags} max={2} fit empty={<span className="text-muted-foreground/60">—</span>} /> },
  { id: "zone", header: "Zone", width: 150, hideBelow: 1000, sortKey: "zone", cell: (c) => c.zone || "—" },
  { id: "rep", header: "Commercial", width: 140, hideBelow: 1400, muted: true, sortKey: "rep", cell: (c) => c.salesRep || "—" },
  { id: "outstanding", header: "Encours", width: 120, numeric: true, sortKey: "outstanding", cell: (c) => <Money value={c.outstanding} zeroMuted /> },
  {
    id: "overdue", header: "En retard", width: 120, numeric: true, sortKey: "overdue",
    cell: (c) => <Money value={c.overdue} zeroMuted tone={c.overdue > 0 ? "destructive" : undefined} />,
  },
  { id: "last", header: "Dernière cde", width: 130, hideBelow: 1000, sortKey: "last", cell: (c) => <DateLabel date={c.lastOrderAt} className="text-secondary-foreground" /> },
  { id: "status", header: "Statut", width: 110, sortKey: "status", cell: (c) => <StatusDot kind="client" value={c.status} /> },
];

export default function ClientsPage() {
  const navigate = useNavigate();
  const [q, setQ] = useUrlState("q");
  const [type, setType] = useUrlState("type");
  const [zone, setZone] = useUrlState("zone");
  const [status, setStatus] = useUrlState("status");
  const [tag, setTag] = useUrlState("tag");
  const { data: tagDefs } = useTags("client");
  const tagOptions = useMemo(() => (tagDefs ?? []).map((t) => ({ value: t.id, label: `${t.label} (${t.count})` })), [tagDefs]);
  const [creating, setCreating] = useState(false);
  const dq = useDebounced(q, 200);

  const list = useServerList({ defaultSort: { id: "name", dir: "asc" } });
  const { data: page, isLoading, isError, refetch } = useClientsPage({
    q: dq, type: type as ClientType, zone, status: status as ClientSummary["status"], tag, ...list.params,
  });
  const data = page?.items;
  const total = page?.total ?? 0;
  // Zone options and tab counts come with the page (facets + counts per status, ignoring the status tab).
  const zones = useMemo(() => (page?.facets?.zone ?? []).map((z) => ({ value: z, label: z })), [page?.facets?.zone]);
  const counts = useMemo(() => {
    const m: Record<string, number> = { ...(page?.counts ?? {}) };
    m[""] = Object.values(page?.counts ?? {}).reduce((a, b) => a + b, 0);
    return m;
  }, [page?.counts]);

  const filtered = !!(dq || type || zone || status || tag);
  const reset = () => { setQ(""); setType(""); setZone(""); setStatus(""); setTag(""); };

  return (
    <Page>
      <PageHeader
        title="Clients"
        tabs={
          <Tabs<StatusTab>
            value={status as StatusTab}
            onChange={setStatus}
            items={STATUS_TABS.map((t) => ({ ...t, count: page ? counts[t.id] ?? 0 : undefined }))}
          />
        }
        filters={
          <>
            <SearchInput value={q} onChange={setQ} placeholder="Nom, code, ville…" />
            <Select size="sm" value={type} onChange={setType} placeholder="Tous les types" options={TYPE_OPTIONS} />
            <Select size="sm" value={zone} onChange={setZone} placeholder="Toutes les zones" options={zones} />
            <Select size="sm" value={tag} onChange={setTag} placeholder="Tous les groupes" options={tagOptions} aria-label="Groupe" />
          </>
        }
        actions={<Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Nouveau client</Button>}
      />
      <PageBody flush>
        {isError && !data ? (
          <EmptyState icon={Users} title="Clients indisponibles" description="L'API ne répond pas. Vérifiez que le serveur tourne sur le port 4000." action={<Button size="sm" onClick={() => refetch()}>Réessayer</Button>} />
        ) : (
          <DataTable
            columns={COLUMNS}
            rows={data}
            server={{ list, total: page?.total }}
            loading={isLoading}
            getRowId={(c) => c.id}
            onRowClick={(c) => navigate(`/clients/${c.id}`)}
            footer={data ? `${total} client${total > 1 ? "s" : ""}${filtered ? " · filtrés" : ""}` : undefined}
            empty={
              filtered ? (
                <EmptyState icon={Users} title="Aucun client ne correspond" description="Modifiez la recherche ou les filtres." action={<Button size="sm" onClick={reset}>Effacer les filtres</Button>} />
              ) : (
                <EmptyState icon={Users} title="Aucun client" description="Les clients du data pack apparaîtront ici." action={<Button size="sm" icon={Plus} onClick={() => setCreating(true)}>Nouveau client</Button>} />
              )
            }
          />
        )}
      </PageBody>
      {creating ? <NewClientPanel zones={zones.map((z) => z.value)} onClose={() => setCreating(false)} /> : null}
    </Page>
  );
}

function NewClientPanel({ zones, onClose }: { zones: string[]; onClose: () => void }) {
  const navigate = useNavigate();
  const [form, setForm] = useState({ name: "", type: "restaurant" as ClientType, zone: zones[0] ?? "", city: "", address: "", salesRep: "" });
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));
  const create = useApiMutation(api.clients.create, {
    success: (c) => `Client ${c.name} créé`,
    invalidate: [qk.clients.all],
    onSuccess: (c) => { onClose(); navigate(`/clients/${c.id}`); },
  });
  const submit = (e: React.FormEvent) => { e.preventDefault(); if (form.name.trim()) create.mutate({ ...form, name: form.name.trim(), status: "prospect" }); };

  return (
    <SidePanel
      title="Nouveau client"
      subtitle="Créé en statut prospect"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Annuler</Button>
          <Button variant="primary" type="submit" form="new-client" loading={create.isPending} disabled={!form.name.trim()}>Créer</Button>
        </>
      }
    >
      <form id="new-client" onSubmit={submit} className="flex flex-col gap-3.5">
        <Field label="Nom"><Input autoFocus value={form.name} onChange={(e) => set("name")(e.target.value)} placeholder="Le Bistrot du Port" /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Type"><Select value={form.type} onChange={set("type")} options={TYPE_OPTIONS} className="w-full" /></Field>
          <Field label="Zone de livraison">
            {zones.length ? <Select value={form.zone} onChange={set("zone")} options={zones.map((z) => ({ value: z, label: z }))} className="w-full" />
              : <Input value={form.zone} onChange={(e) => set("zone")(e.target.value)} />}
          </Field>
        </div>
        <Field label="Adresse"><Input value={form.address} onChange={(e) => set("address")(e.target.value)} /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Ville"><Input value={form.city} onChange={(e) => set("city")(e.target.value)} /></Field>
          <Field label="Commercial"><Input value={form.salesRep} onChange={(e) => set("salesRep")(e.target.value)} /></Field>
        </div>
      </form>
    </SidePanel>
  );
}
