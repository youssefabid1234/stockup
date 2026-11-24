/**
 * Historique — every client + supplier event across the company (GET /client-events, /supplier-events).
 * Tabs Clients / Fournisseurs, filters in the URL (famille, statut, du/au, recherche), server-side filtering AND
 * pagination (one page of 100; stats from the Page extras), rows link to the entity, inline "Marquer résolu".
 * Live: client_event.* / supplier_event.* refresh qk.history.
 */
import { useMemo } from "react";
import { History } from "lucide-react";
import { api } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import { qk, useApiMutation, useClientEventSearch, useSupplierEventSearch } from "@/lib/queries";
import { useDebounced, useUrlState } from "@/lib/url-state";
import { Button, DatePicker, EmptyState, Page, PageBody, PageHeader, SearchInput, Segmented, Stat, StatGrid, Tabs, useServerList } from "@/ui";
import { EventTimeline, FAMILIES, FamilyChips, typesOfFamilies, type EventKind, type FamilyId, type TimelineEvent } from "./timeline";

const ISSUE_TYPES = new Set<string>(FAMILIES.find((f) => f.id === "issues")?.types ?? []);


export default function HistoryPage() {
  const [kindRaw, setKind] = useUrlState("kind", "client");
  const kind: EventKind = kindRaw === "supplier" ? "supplier" : "client";
  const [family, setFamily] = useUrlState("family");
  const families = useMemo(() => (family ? (family.split(",") as FamilyId[]) : []), [family]);
  const toggleFamily = (f: FamilyId) => setFamily((families.includes(f) ? families.filter((x) => x !== f) : [...families, f]).join(","));
  const [status, setStatus] = useUrlState("status");
  const [from, setFrom] = useUrlState("from");
  const [to, setTo] = useUrlState("to");
  const [q, setQ] = useUrlState("q");
  const dq = useDebounced(q, 250);

  const list = useServerList({ pageKey: "histPage", defaultSort: { id: "at", dir: "desc" } });
  const params = {
    type: families.length ? typesOfFamilies(families, kind) : undefined,
    status: (status || undefined) as "open" | "resolved" | undefined,
    q: dq || undefined,
    from: from || undefined,
    to: to || undefined,
    ...list.params,
  };
  const clients = useClientEventSearch(params, kind === "client");
  const suppliers = useSupplierEventSearch(params, kind === "supplier");
  const cur = kind === "client" ? clients : suppliers;
  const page = cur.data;
  const events = page?.items as TimelineEvent[] | undefined;

  // Tab counts: the size of each unfiltered history (one row fetched, the total is what matters).
  const allClients = useClientEventSearch({ limit: 1 });
  const allSuppliers = useSupplierEventSearch({ limit: 1 });

  const resolve = useApiMutation(
    ({ ev, resolution }: { ev: TimelineEvent; resolution: string }): Promise<unknown> =>
      "clientId" in ev
        ? api.clientEvents.update(ev.id, { status: "resolved", ...(resolution ? { resolution } : {}) })
        : api.supplierEvents.update(ev.id, { status: "resolved", ...(resolution ? { resolution } : {}) }),
    { success: "Event resolved", invalidate: [qk.history.all, qk.clients.all, qk.suppliers.all] },
  );

  // Stats over the whole filtered set (Page extras), not just the page.
  const stats = useMemo(() => {
    const byType = page?.countsByType ?? {};
    const issues = Object.entries(byType).reduce((n, [t, c]) => n + (ISSUE_TYPES.has(t) ? c : 0), 0);
    const open = status === "resolved" ? 0 : page?.counts?.open ?? 0;
    return { total: page?.total ?? 0, open, issues, amount: page?.sums?.amount ?? 0 };
  }, [page, status]);

  const filtered = !!(family || status || from || to || dq);
  const reset = () => { setFamily(""); setStatus(""); setFrom(""); setTo(""); setQ(""); };

  return (
    <Page>
      <PageHeader
        title="Background"
        tabs={
          <Tabs
            value={kind}
            onChange={(k) => setKind(k)}
            items={[
              { id: "client" as const, label: "Customers", count: allClients.data?.total },
              { id: "supplier" as const, label: "Suppliers", count: allSuppliers.data?.total },
            ]}
          />
        }
        filters={
          <>
            <SearchInput value={q} onChange={setQ} placeholder="Title, description..." />
            <DatePicker size="sm" value={from} onChange={setFrom} max={to || undefined} placeholder="From" clearable presets={[{ label: "−30 j", days: -30 }, { label: "−1 an", days: -365 }]} aria-label="From" className="w-[120px]" />
            <DatePicker size="sm" value={to} onChange={setTo} min={from || undefined} placeholder="To" clearable presets={[{ label: "Today", days: 0 }]} aria-label="To" className="w-[120px]" />
          </>
        }
      />
      <PageBody flush>
        <StatGrid className="md:grid-cols-4">
          <Stat label="Events" value={<span className="num">{stats.total}</span>} hint={filtered ? "Depending on the filters" : kind === "client" ? "All customers" : "All suppliers"} />
          <Stat label="Open" value={<span className="num">{stats.open}</span>} tone={stats.open ? "warning" : undefined} hint="To be processed"
            onClick={() => setStatus(status === "open" ? "" : "open")} />
          <Stat label="Claims & quality" value={<span className="num">{stats.issues}</span>}
            onClick={() => setFamily(family === "issues" ? "" : "issues")} />
          <Stat label="Amounts involved" value={fmtMoney(stats.amount, { compact: true })} hint="Assets, disputes, debts" />
        </StatGrid>
        <div className="px-5 py-4">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <FamilyChips value={families} onToggle={toggleFamily} onClear={() => setFamily("")} />
            <Segmented
              className="ml-auto"
              value={(status || "all") as "all" | "open" | "resolved"}
              onChange={(v) => setStatus(v === "all" ? "" : v)}
              options={[{ id: "all", label: "All" }, { id: "open", label: "Open" }, { id: "resolved", label: "Solved" }]}
            />
          </div>
          <EventTimeline
            kind={kind}
            events={events}
            total={page?.total}
            pageKey={list.pageKey}
            loading={cur.isLoading}
            toolbar={false}
            showEntity
            onResolve={(ev, resolution) => resolve.mutate({ ev, resolution })}
            resolvingId={resolve.isPending ? resolve.variables?.ev.id : undefined}
            empty={
              <EmptyState
                icon={History}
                title={filtered ? "No event matching" : "No history"}
                description={filtered ? "Change filters or period." : "Appeals, claims, returns and negotiations will appear here."}
                action={filtered ? <Button size="sm" onClick={reset}>Clear Filters</Button> : undefined}
              />
            }
          />
        </div>
      </PageBody>
    </Page>
  );
}
