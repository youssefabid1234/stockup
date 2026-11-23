/**
 * Shared list frame for sale orders and purchase orders: status tabs with counts, search (number or partner), date filter
 * (DatePicker with presets, clearable = toutes dates), one extra filter (sale: channel; purchase: supplier),
 * same columns (number, partner, date, lines, total, status), "Nouvelle commande" picker, footer with totals.
 * Server-side: the page fetches ONE page with every filter + sort (useDocListFilters gives the URL state and the
 * API params), and passes the rows of the page, the total, the tab counts and the footer total from the API Page.
 */
import { useMemo, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import { todayIso } from "@/lib/format";
import { useMeta } from "@/lib/queries";
import { useDebounced, useUrlState } from "@/lib/url-state";
import {
  Button, DataTable, DateLabel, DatePicker, EmptyState, Money, Mono, Page, PageBody, PageHeader, SearchInput, StatusDot, Tabs, useServerList, type Column,
} from "@/ui";
import { NewDocumentButton } from "./create";
import { KIND, type DocKind } from "./model";

export interface DocRow {
  id: string;
  number: string;
  partnerName: string;
  date: string;
  lineCount: number;
  totalHt: number;
  status: string;
  /** Shown after the partner name (sale: voice-agent channel). */
  partnerExtra?: ReactNode;
  /** Date shown in red with "en retard" (purchase: open and past expected date). */
  late?: boolean;
}

const DATE_PRESETS = [{ label: "Hier", days: -1 }, { label: "Aujourd'hui", days: 0 }, { label: "Demain", days: 1 }];

/** "YYYY-MM-DD" + n days, local. */
export function addDaysIso(iso: string, n: number): string {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(y, m - 1, d + n);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
}

/** URL-backed list filters shared by both lists: status tab, search, date (today | tomorrow | ISO), partner. */
export function useDocListFilters(partnerKey: string) {
  const { data: meta } = useMeta();
  const today = meta?.today ?? todayIso();
  const [status, setStatus] = useUrlState("status");
  const [q, setQ] = useUrlState("q");
  const [date, setDate] = useUrlState("date");
  const [partner, setPartner] = useUrlState(partnerKey);
  const [newParam, setNewParam] = useUrlState("new", "", { keepPage: true });
  const dq = useDebounced(q, 200);
  // "today" / "tomorrow" are relative to the business date (data pack), anything else is an ISO date.
  const isoDate = date === "today" ? today : date === "tomorrow" ? addDaysIso(today, 1) : date || undefined;
  // Page + sort in the URL (?page=, ?sort=-date); default = newest number first.
  const list = useServerList({ defaultSort: { id: "number", dir: "desc" } });
  /** API params of the current page: status tab, search, date + page / sort (the partner / extra filter are added by the page). */
  const params = { status: status || undefined, q: dq || undefined, date: isoDate, ...list.params };
  return { today, status, setStatus, q, setQ, dq, date, setDate, isoDate, partner, setPartner, newParam, setNewParam, list, params };
}
export type DocListFilters = ReturnType<typeof useDocListFilters>;

export function DocumentListPage({ kind, title, icon: Icon, tabs, filters: f, rows, total, counts, totalHt, loading, error, onRetry, extraFilter, extraActive, onResetExtra, emptyText }: {
  kind: DocKind;
  title: string;
  icon: LucideIcon;
  tabs: readonly { id: string; label: string }[];
  filters: DocListFilters;
  /** Rows of the current page (every filter, sort and page applied by the API). */
  rows?: DocRow[];
  /** Rows matching the filters (Page.total). */
  total?: number;
  /** Rows per status, ignoring the status tab (Page.counts). */
  counts?: Record<string, number>;
  /** Σ total HT of the filtered rows (Page.sums.totalHt). */
  totalHt?: number;
  loading: boolean;
  error: boolean;
  onRetry: () => void;
  /** The one extra filter of the list (sale: channel; purchase: supplier). */
  extraFilter?: ReactNode;
  extraActive?: boolean;
  onResetExtra?: () => void;
  emptyText: string;
}) {
  const navigate = useNavigate();
  const k = KIND[kind];
  const sale = kind === "sale";
  const tabCount = (id: string) => (counts ? (id ? counts[id] ?? 0 : Object.values(counts).reduce((a, b) => a + b, 0)) : undefined);

  const columns = useMemo<Column<DocRow>[]>(() => [
    { id: "number", header: "N°", width: 170, sortKey: "number", cell: (r) => <Mono>{r.number}</Mono> },
    {
      id: "partner", header: k.partner, sortKey: sale ? "client" : "supplier",
      cell: (r) => <span className="flex min-w-0 items-center gap-2"><span className="truncate font-medium">{r.partnerName}</span>{r.partnerExtra}</span>,
    },
    {
      id: "date", header: k.date, width: 150, sortKey: "date",
      cell: (r) => <span className={r.late ? "text-destructive" : undefined}><DateLabel date={r.date} />{r.late ? <span className="ml-1.5 text-[12px]">en retard</span> : null}</span>,
    },
    { id: "lines", header: "Lignes", width: 80, numeric: true, muted: true, sortKey: "lines", cell: (r) => r.lineCount },
    { id: "total", header: "Total HT", width: 130, numeric: true, sortKey: "total", cell: (r) => <Money value={r.totalHt} zeroMuted /> },
    { id: "status", header: "Statut", width: 150, sortKey: "status", cell: (r) => <StatusDot kind={sale ? "order" : "purchaseOrder"} value={r.status} /> },
  ], [k, sale]);

  const filtered = !!(f.dq || f.date || f.partner || f.status || extraActive);
  const reset = () => { f.setQ(""); f.setDate(""); f.setPartner(""); f.setStatus(""); onResetExtra?.(); };
  const creating = f.newParam === "1";
  const newButton = (size?: "sm") => (
    <NewDocumentButton kind={kind} size={size} variant={size ? "default" : "primary"}
      open={size ? undefined : creating} onOpenChange={size ? undefined : (o) => f.setNewParam(o ? "1" : "")} />
  );

  return (
    <Page>
      <PageHeader
        title={title}
        tabs={<Tabs value={f.status} onChange={f.setStatus} items={tabs.map((t) => ({ ...t, count: tabCount(t.id) }))} />}
        actions={newButton()}
        filters={
          <>
            <SearchInput value={f.q} onChange={f.setQ} placeholder={`N° ou ${k.partner.toLowerCase()}…`} className="w-[200px]" />
            <DatePicker size="sm" value={f.isoDate ?? ""} onChange={f.setDate} placeholder="Toutes dates" presets={DATE_PRESETS} clearable
              aria-label={k.date} className="w-[150px]" />
            {extraFilter}
            {filtered ? <Button size="sm" variant="ghost" onClick={reset} className="ml-auto">Effacer les filtres</Button> : null}
          </>
        }
      />
      <PageBody flush>
        {error && !rows ? (
          <EmptyState icon={Icon} title={`${title} indisponibles`} description="L'API ne répond pas. Vérifiez que le serveur tourne sur le port 4000." action={<Button size="sm" onClick={onRetry}>Réessayer</Button>} />
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            server={{ list: f.list, total }}
            loading={loading}
            getRowId={(r) => r.id}
            onRowClick={(r) => navigate(`${k.detailPath}/${r.id}`)}
            footer={total !== undefined ? <>{total} commande{total > 1 ? "s" : ""}{filtered ? " · filtrées" : ""} · <Money value={totalHt ?? 0} /> HT</> : undefined}
            empty={
              filtered ? (
                <EmptyState icon={Icon} title="Aucune commande ne correspond" description="Modifiez la recherche ou les filtres." action={<Button size="sm" onClick={reset}>Effacer les filtres</Button>} />
              ) : (
                <EmptyState icon={Icon} title="Aucune commande" description={emptyText} action={newButton("sm")} />
              )
            }
          />
        )}
      </PageBody>
    </Page>
  );
}
