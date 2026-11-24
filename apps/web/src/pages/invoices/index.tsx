/** Factures — server-paginated list (useInvoicesPage: one page of 100), status tabs with counts + balances, search by
 *  number/client, sort, footer totals — all computed by the API over the whole filtered set. */
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { FileText } from "lucide-react";
import type { InvoiceSummary } from "@kit/shared";
import { useInvoicesPage } from "@/lib/queries";
import { useDebounced, useUrlPatch, useUrlState } from "@/lib/url-state";
import {
  Button, DataTable, DateLabel, EmptyState, Money, Mono, Page, PageBody, PageHeader, SearchInput, StatusDot, Tabs, useServerList, type Column,
} from "@/ui";

/** Tabs = (effective) statuses sent to the API; "all" = no status filter. */
const TABS = [
  { id: "open", label: "Payable", statuses: ["issued", "partially_paid"] },
  { id: "overdue", label: "Overdue", statuses: ["overdue"] },
  { id: "paid", label: "Paid", statuses: ["paid"] },
  { id: "all", label: "All", statuses: [] },
] as const;
type TabId = (typeof TABS)[number]["id"];

const COLUMNS: Column<InvoiceSummary>[] = [
  { id: "number", header: "N°", width: 170, sortKey: "number", cell: (i) => <Mono>{i.number}</Mono> },
  { id: "client", header: "Customer", sortKey: "client", cell: (i) => <span className="truncate font-medium">{i.clientName}</span> },
  { id: "issued", header: "Issued", width: 115, hideBelow: 1000, sortKey: "issued", cell: (i) => <DateLabel date={i.issuedAt} className="text-secondary-foreground" /> },
  {
    id: "due", header: "Due date", width: 150, sortKey: "due",
    cell: (i) => (
      <span className={i.daysOverdue > 0 ? "text-destructive" : undefined}>
        <DateLabel date={i.dueDate} />
        {i.daysOverdue > 0 ? <span className="num ml-1.5 text-[12px]">+{i.daysOverdue} j</span> : null}
      </span>
    ),
  },
  { id: "ttc", header: "Total TTC", width: 120, hideBelow: 900, numeric: true, sortKey: "ttc", cell: (i) => <Money value={i.totalTtc} /> },
  { id: "paid", header: "Paid", width: 115, hideBelow: 1000, numeric: true, sortKey: "paid", cell: (i) => <Money value={i.amountPaid} zeroMuted /> },
  {
    id: "balance", header: "Remains due", width: 120, numeric: true, sortKey: "balance",
    cell: (i) => <Money value={i.balance} zeroMuted className="font-medium" tone={i.daysOverdue > 0 ? "destructive" : undefined} />,
  },
  { id: "status", header: "Status", width: 160, sortKey: "status", cell: (i) => <StatusDot kind="invoice" value={i.status} /> },
];

export default function InvoicesPage() {
  const navigate = useNavigate();
  const [tab] = useUrlState("tab", "open");
  const patch = useUrlPatch();
  const [q, setQ] = useUrlState("q");
  const dq = useDebounced(q, 150);
  const current = TABS.find((t) => t.id === tab) ?? TABS[0];
  const list = useServerList({ defaultSort: current.id === "overdue" ? { id: "due", dir: "asc" } : { id: "issued", dir: "desc" } });
  // A new tab also drops the column sort (each tab has its own default order).
  const setTab = (id: TabId) => patch({ tab: id === "open" ? "" : id, sort: "" });

  const { data, isLoading, isError, refetch } = useInvoicesPage({ status: current.statuses.join(",") || undefined, q: dq || undefined, ...list.params });

  // Tab badges: counts + balances per status over every invoice matching the search (ignoring the tab).
  const stats = useMemo(() => {
    const m = {} as Record<TabId, { count: number; balance: number }>;
    const counts = data?.counts ?? {};
    const sums = data?.sumsByStatus ?? {};
    for (const t of TABS) {
      const statuses: readonly string[] = t.id === "all" ? Object.keys(counts) : t.statuses;
      m[t.id] = {
        count: statuses.reduce((n, st) => n + (counts[st] ?? 0), 0),
        balance: statuses.reduce((n, st) => n + (t.id === "paid" ? sums[st]?.totalTtc ?? 0 : sums[st]?.balance ?? 0), 0),
      };
    }
    return m;
  }, [data]);

  const rows = data?.items;
  const total = data?.total ?? 0;
  const totals = { ttc: data?.sums?.totalTtc ?? 0, paid: data?.sums?.amountPaid ?? 0, balance: data?.sums?.balance ?? 0 };

  return (
    <Page>
      <PageHeader
        title="Invoices"
        tabs={
          <Tabs<TabId>
            value={current.id}
            onChange={setTab}
            items={TABS.map((t) => ({
              id: t.id,
              label: (
                <>
                  {t.label}
                  {data ? (
                    <span className="num text-[11.5px] font-normal text-muted-foreground">
                      {stats[t.id].count}
                      {t.id !== "all" && stats[t.id].count ? <> · <Money value={stats[t.id].balance} compact className={t.id === "overdue" ? "text-destructive" : undefined} /></> : null}
                    </span>
                  ) : null}
                </>
              ),
            }))}
          />
        }
        filters={<SearchInput value={q} onChange={setQ} placeholder="Bill number, customer..." />}
      />
      <PageBody flush>
        {isError && !data ? (
          <EmptyState icon={FileText} title="Invoices not available" description="TheAPI Check that the server is running on port 4000." action={<Button size="sm" onClick={() => refetch()}>Retry</Button>} />
        ) : (
          <DataTable
            columns={COLUMNS}
            rows={rows}
            server={{ list, total: data?.total }}
            loading={isLoading}
            getRowId={(i) => i.id}
            onRowClick={(i) => navigate(`/invoices/${i.id}`)}
            footer={rows ? (
              <span className="flex flex-wrap items-center gap-x-5 gap-y-1">
                <span>{total} facture{total > 1 ? "s" : ""}{dq ? " · filtered" : ""}</span>
                <span className="ml-auto">Total TTC <Money value={totals.ttc} className="font-medium text-foreground" /></span>
                <span>Paid <Money value={totals.paid} className="font-medium text-foreground" /></span>
                <span>Remains due <Money value={totals.balance} className="font-medium text-foreground" /></span>
              </span>
            ) : undefined}
            empty={
              dq ? (
                <EmptyState icon={FileText} title="No invoice matching" description="Change the search." action={<Button size="sm" onClick={() => setQ("")}>Clear Search</Button>} />
              ) : (
                <EmptyState icon={FileText} title={current.id === "overdue" ? "No invoice late" : "No invoice"} description="Invoices are created from an order delivered." />
              )
            }
          />
        )}
      </PageBody>
    </Page>
  );
}
