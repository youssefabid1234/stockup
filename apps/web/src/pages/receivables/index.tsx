/**
 * Encours — client receivables / aged balance (GET /api/receivables).
 *  - header: title + as-of date · filters (search, groupe, commercial, zone, "En retard uniquement"),
 *  - KPI strip (encours, échu, DSO, clients en retard) + stacked aging bar (click a bucket → filter rows),
 *  - DataTable per client (sortable, paginated, footer totals of the filtered list),
 *  - row click → ReceivablePanel (invoices, payments, disputes, reminders, actions).
 * Live: the query lives under the clients root, so client / order / invoice / payment events refresh it.
 */
import { useMemo } from "react";
import { Check, Scale } from "lucide-react";
import type { AgingBuckets, ReceivableRow } from "@kit/shared";
import { useReceivables, useTags } from "@/lib/queries";
import { useDebounced, useUrlState } from "@/lib/url-state";
import { cn } from "@/lib/cn";
import { fmtDate, parseDate } from "@/lib/format";
import {
  Button, DataTable, Dot, EmptyState, Money, Mono, Page, PageBody, PageHeader, SearchInput, Select, Stat, StatusDot,
  type Column,
} from "@/ui";
import { AgingStrip, BUCKETS, CreditUse, MiniAging, RISK, isBucket, type BucketId } from "./aging";
import { ReceivablePanel } from "./panel";

/** "Karim Benali" → "Karim B." */
const shortName = (s: string) => { const [first, ...rest] = (s || "").trim().split(/\s+/); return first ? (rest.length ? `${first} ${rest[rest.length - 1][0]}.` : first) : "—"; };
const days = (n?: number) => (n == null ? "—" : `${n} j`);
/** "26 oct." — compact date for dense columns (weekday dropped). */
const dm = new Intl.DateTimeFormat("fr-FR", { day: "numeric", month: "short" });
const Dm = ({ date, className }: { date?: string; className?: string }) => (date ? <span className={cn("num whitespace-nowrap", className)} title={fmtDate(date)}>{dm.format(parseDate(date))}</span> : <span className="text-muted-foreground/60">—</span>);

const COLUMNS: Column<ReceivableRow>[] = [
  {
    id: "client", header: "Client", sortValue: (r) => r.clientName,
    cell: (r) => (
      <span className="flex min-w-0 items-center gap-2">
        {r.status === "blocked" ? <span title="Client bloqué" className="flex"><Dot tone="destructive" /></span> : null}
        <span className="min-w-0 truncate font-medium" title={r.clientName}>{r.clientName}</span>
        <Mono className="shrink-0 text-muted-foreground">{r.clientCode}</Mono>
      </span>
    ),
  },
  { id: "rep", header: "Commercial", width: 96, hideBelow: 1000, muted: true, sortValue: (r) => r.salesRep, cell: (r) => <span className="block truncate" title={r.salesRep}>{shortName(r.salesRep)}</span> },
  { id: "outstanding", header: "Encours", width: 94, numeric: true, sortValue: (r) => r.outstanding, cell: (r) => <Money value={r.outstanding} zeroMuted className="font-medium" /> },
  {
    id: "overdue", header: "Échu", width: 92, numeric: true, sortValue: (r) => r.overdue,
    cell: (r) => <Money value={r.overdue} zeroMuted tone={r.overdue > 0 ? "destructive" : undefined} />,
  },
  { id: "aging", header: "Balance", width: 68, sortValue: (r) => r.maxDaysOverdue, cell: (r) => <MiniAging buckets={r.buckets} /> },
  {
    id: "credit", header: "Plafond", width: 124, sortValue: (r) => (r.creditLimit ? r.outstanding / r.creditLimit : -1),
    cell: (r) => (
      <span className="flex min-w-0 items-center gap-2.5">
        <Money value={r.creditLimit || null} compact className="w-[52px] shrink-0 text-right text-[12px] text-secondary-foreground" />
        <CreditUse row={r} className="flex-1" />
      </span>
    ),
  },
  {
    id: "oldest", header: <span title="Plus vieille échéance impayée">Plus ancienne</span>, width: 108, sortValue: (r) => r.oldestDueDate ?? "",
    cell: (r) => r.oldestDueDate ? (
      <span className={r.maxDaysOverdue > 0 ? "text-destructive" : "text-secondary-foreground"}>
        <Dm date={r.oldestDueDate} />
        {r.maxDaysOverdue > 0 ? <span className="num ml-1.5 text-[12px]">+{r.maxDaysOverdue} j</span> : null}
      </span>
    ) : <span className="text-muted-foreground/60">—</span>,
  },
  {
    id: "lastPayment", header: "Dern. paiement", width: 116, hideBelow: 1100, sortValue: (r) => r.lastPaymentAt ?? "",
    cell: (r) => r.lastPaymentAt ? (
      <span className="flex items-baseline gap-1.5">
        <Dm date={r.lastPaymentAt} className="text-secondary-foreground" />
        <Money value={r.lastPaymentAmount} compact className="text-[12px] text-muted-foreground" />
      </span>
    ) : <span className="text-muted-foreground/60">—</span>,
  },
  {
    id: "avg", header: <span title="Délai moyen de paiement (90 derniers jours)">Délai</span>, width: 60, hideBelow: 1000, numeric: true, sortValue: (r) => r.avgDaysToPay ?? null,
    cell: (r) => <span className={cn(r.avgDaysToPay != null && r.avgDaysToPay > r.paymentTermsDays + 15 ? "text-warning" : "text-secondary-foreground")} title={`Conditions : ${r.paymentTermsDays} j`}>{days(r.avgDaysToPay)}</span>,
  },
  {
    id: "disputes", header: "Litiges", width: 54, hideBelow: 1000, numeric: true, sortValue: (r) => r.openDisputes,
    cell: (r) => r.openDisputes ? <span className="font-medium text-warning">{r.openDisputes}</span> : <span className="text-muted-foreground/60">0</span>,
  },
  {
    id: "reminder", header: "Relance", width: 66, hideBelow: 1000, sortValue: (r) => r.lastReminderAt ?? "",
    cell: (r) => <Dm date={r.lastReminderAt} className="text-secondary-foreground" />,
  },
  { id: "risk", header: "Risque", width: 104, sortValue: (r) => RISK[r.risk].rank, cell: (r) => <StatusDot tone={RISK[r.risk].tone} label={RISK[r.risk].label} /> },
];

const ZERO: AgingBuckets = { current: 0, d1_30: 0, d31_60: 0, d61_90: 0, d90plus: 0 };

export default function ReceivablesPage() {
  const [q, setQ] = useUrlState("q");
  const [tag, setTag] = useUrlState("tag");
  const [rep, setRep] = useUrlState("rep");
  const [zone, setZone] = useUrlState("zone");
  const [overdueOnly, setOverdueOnly] = useUrlState("overdue");
  const [bucketParam, setBucket] = useUrlState("bucket");
  const [sel, setSel] = useUrlState("p", "", { keepPage: true });
  const bucket: BucketId | "" = isBucket(bucketParam) ? bucketParam : "";
  const dq = useDebounced(q, 200);

  const { data, isLoading, isError, refetch } = useReceivables({ q: dq, tag, rep, zone, onlyOverdue: overdueOnly === "1" || undefined });
  // Unfiltered (cached) → option lists for Commercial / Zone.
  const { data: all } = useReceivables();
  const { data: tagDefs } = useTags("client");
  const tagOptions = useMemo(() => (tagDefs ?? []).map((t) => ({ value: t.id, label: t.label })), [tagDefs]);
  const repOptions = useMemo(() => [...new Set((all?.rows ?? []).map((r) => r.salesRep).filter(Boolean))].sort().map((v) => ({ value: v, label: v })), [all]);
  const zoneOptions = useMemo(() => [...new Set((all?.rows ?? []).map((r) => r.zone).filter(Boolean))].sort().map((v) => ({ value: v, label: v })), [all]);

  const rows = useMemo(() => (data ? (bucket ? data.rows.filter((r) => r.buckets[bucket] > 0.004) : data.rows) : undefined), [data, bucket]);
  const foot = useMemo(() => (rows ?? []).reduce(
    (s, r) => ({ outstanding: s.outstanding + r.outstanding, overdue: s.overdue + r.overdue, bucket: s.bucket + (bucket ? r.buckets[bucket] : 0), late: s.late + (r.overdue > 0 ? 1 : 0) }),
    { outstanding: 0, overdue: 0, bucket: 0, late: 0 },
  ), [rows, bucket]);
  const selected = useMemo(() => data?.rows.find((r) => r.clientId === sel) ?? all?.rows.find((r) => r.clientId === sel), [data, all, sel]);

  const t = data?.totals;
  const filtered = !!(dq || tag || rep || zone || overdueOnly || bucket);
  const reset = () => { setQ(""); setTag(""); setRep(""); setZone(""); setOverdueOnly(""); setBucket(""); };

  return (
    <Page>
      <PageHeader
        title="Encours"
        meta={data ? <span className="whitespace-nowrap text-[12px] text-muted-foreground" title={fmtDate(data.asOf)}>au {dm.format(parseDate(data.asOf))}</span> : undefined}
        filters={
          <>
            <SearchInput value={q} onChange={setQ} placeholder="Client, code…" className="w-[168px] shrink-0" />
            <Select size="sm" value={tag} onChange={setTag} placeholder="Groupe" options={tagOptions} aria-label="Groupe" className="w-[128px] shrink-0" />
            <Select size="sm" value={rep} onChange={setRep} placeholder="Commercial" options={repOptions} aria-label="Commercial" className="w-[136px] shrink-0" />
            <Select size="sm" value={zone} onChange={setZone} placeholder="Zone" options={zoneOptions} aria-label="Zone" className="w-[124px] shrink-0" />
            <button
              type="button"
              role="switch"
              aria-checked={overdueOnly === "1"}
              onClick={() => setOverdueOnly(overdueOnly === "1" ? "" : "1")}
              className={cn(
                "flex h-7 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[4px] border px-2 text-[12.5px] transition-colors",
                overdueOnly === "1" ? "border-destructive/30 bg-destructive/10 text-destructive" : "border-input text-muted-foreground hover:border-border-hover hover:text-foreground",
              )}
            >
              <span className={cn("flex h-3.5 w-3.5 items-center justify-center rounded-[3px] border", overdueOnly === "1" ? "border-destructive bg-destructive text-card" : "border-input")}>
                {overdueOnly === "1" ? <Check size={10} strokeWidth={3} /> : null}
              </span>
              En retard uniquement
            </button>
          </>
        }
      />
      <PageBody flush>
        {isError && !data ? (
          <EmptyState icon={Scale} title="Encours indisponible" description="L'API ne répond pas. Vérifiez que le serveur tourne sur le port 4000." action={<Button size="sm" onClick={() => refetch()}>Réessayer</Button>} />
        ) : (
          <>
            <div className="grid grid-cols-2 border-b border-border xl:grid-cols-[repeat(4,minmax(0,1fr))_minmax(0,2.4fr)]">
              <Stat label="Encours total" value={t ? <Money value={t.outstanding} compact /> : "—"} hint={t ? `${t.clients} client${t.clients > 1 ? "s" : ""}` : undefined} className="border-r border-border" />
              <Stat
                label="Échu"
                value={t ? <Money value={t.overdue} compact /> : "—"}
                tone={t && t.overdue > 0 ? "destructive" : undefined}
                hint={t && t.outstanding ? `${Math.round((t.overdue / t.outstanding) * 100)} % de l'encours` : undefined}
                className="xl:border-r xl:border-border"
              />
              <Stat label="DSO" value={t ? <>{t.dso}<span className="ml-1 text-[13px] font-normal text-muted-foreground">jours</span></> : "—"} hint="Délai d'encaissement" className="border-r border-t border-border xl:border-t-0" />
              <Stat
                label="Clients en retard"
                value={t ? <>{t.clientsOverdue}<span className="ml-1 text-[13px] font-normal text-muted-foreground">/ {t.clients}</span></> : "—"}
                tone={t && t.clientsOverdue > 0 ? "warning" : undefined}
                hint={overdueOnly === "1" ? "Filtre actif · retirer" : "Afficher uniquement"}
                onClick={() => setOverdueOnly(overdueOnly === "1" ? "" : "1")}
                className="border-t border-border xl:border-r xl:border-t-0"
              />
              <div className="col-span-2 border-t border-border xl:col-span-1 xl:border-t-0">
                <AgingStrip buckets={t ?? ZERO} active={bucket} onSelect={setBucket} />
              </div>
            </div>
            <DataTable
              columns={COLUMNS}
              rows={rows}
              loading={isLoading}
              getRowId={(r) => r.clientId}
              className="[&_table]:table-fixed [&_td]:overflow-hidden"
              selectedId={sel || null}
              onRowClick={(r) => setSel(r.clientId === sel ? "" : r.clientId)}
              defaultSort={{ id: "overdue", dir: "desc" }}
              footer={rows ? (
                <span className="flex flex-wrap items-center gap-x-5 gap-y-1">
                  <span>
                    {rows.length} client{rows.length > 1 ? "s" : ""}{filtered ? " · filtrés" : ""}
                    {bucket ? <> · tranche {BUCKETS.find((b) => b.id === bucket)?.label}</> : null}
                  </span>
                  <span className="ml-auto">Encours <Money value={foot.outstanding} className="font-medium text-foreground" /></span>
                  <span>Échu <Money value={foot.overdue} className="font-medium text-foreground" /></span>
                  {bucket ? <span>{BUCKETS.find((b) => b.id === bucket)?.label} <Money value={foot.bucket} className="font-medium text-foreground" /></span> : null}
                  <span>{foot.late} en retard</span>
                </span>
              ) : undefined}
              empty={
                filtered ? (
                  <EmptyState icon={Scale} title="Aucun client ne correspond" description="Modifiez la recherche ou les filtres." action={<Button size="sm" onClick={reset}>Effacer les filtres</Button>} />
                ) : (
                  <EmptyState icon={Scale} title="Aucun encours" description="Toutes les factures sont réglées." />
                )
              }
            />
          </>
        )}
      </PageBody>
      {sel ? <ReceivablePanel key={sel} clientId={sel} row={selected} onClose={() => setSel("")} /> : null}
    </Page>
  );
}
