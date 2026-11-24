/** Paiements — server-paginated list (usePaymentsPage: search, mode, sort, footer total by the API) + record a payment
 *  (SidePanel, manual or oldest-first allocation). Allocations carry their invoice number (no invoice list needed). */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Wallet } from "lucide-react";
import type { PaymentMethod, PaymentSummary } from "@kit/shared";
import { fmtMoney } from "@/lib/format";
import { PAYMENT_METHOD_LABEL } from "@/lib/labels";
import { usePaymentsPage } from "@/lib/queries";
import { useDebounced, useUrlState } from "@/lib/url-state";
import {
  Button, DataTable, DateLabel, EmptyState, Money, Mono, Page, PageBody, PageHeader, SearchInput, Select, useServerList, type Column,
} from "@/ui";
import { RecordPaymentPanel } from "./RecordPaymentPanel";

const METHOD_OPTIONS = Object.entries(PAYMENT_METHOD_LABEL).map(([value, label]) => ({ value, label }));

export default function PaymentsPage() {
  const [q, setQ] = useUrlState("q");
  const [method, setMethod] = useUrlState("method");
  const [creating, setCreating] = useState(false);
  const dq = useDebounced(q, 150);

  const list = useServerList({ defaultSort: { id: "date", dir: "desc" } });
  const { data, isLoading, isError, refetch } = usePaymentsPage({ q: dq || undefined, method: method || undefined, ...list.params });
  const rows = data?.items;

  const columns: Column<PaymentSummary>[] = useMemo(() => [
    { id: "date", header: "Date", width: 120, sortKey: "date", cell: (p) => <DateLabel date={p.receivedAt} /> },
    {
      id: "client", header: "Client", sortKey: "client",
      cell: (p) => <Link to={`/clients/${p.clientId}`} className="truncate font-medium hover:underline">{p.clientName}</Link>,
    },
    { id: "method", header: "Mode", width: 120, muted: true, sortKey: "method", cell: (p) => PAYMENT_METHOD_LABEL[p.method] ?? p.method },
    { id: "ref", header: "Référence", width: 180, hideBelow: 1000, sortKey: "ref", cell: (p) => (p.reference ? <span className="block w-0 min-w-full truncate" title={p.reference}><Mono>{p.reference}</Mono></span> : <span className="text-muted-foreground">—</span>) },
    { id: "amount", header: "Montant", width: 120, numeric: true, sortKey: "amount", cell: (p) => <Money value={p.amount} className="font-medium" /> },
    {
      id: "alloc", header: "Factures imputées", width: 300,
      cell: (p) => p.allocations.length === 0 ? (
        <span className="text-muted-foreground">Non imputé</span>
      ) : (
        // One line that never widens the column: the first two invoices, then "+N" (full list in its title).
        <span className="flex w-0 min-w-full items-center gap-2.5 overflow-hidden whitespace-nowrap">
          {p.allocations.slice(0, 2).map((a) => (
            <Link key={a.invoiceId} to={`/invoices/${a.invoiceId}`} title={fmtMoney(a.amount)} className="hover:underline">
              <Mono>{a.invoiceNumber ?? a.invoiceId}</Mono>
            </Link>
          ))}
          {p.allocations.length > 2 ? (
            <span className="text-[11.5px] text-muted-foreground" title={p.allocations.slice(2).map((a) => a.invoiceNumber ?? a.invoiceId).join(", ")}>
              +{p.allocations.length - 2}
            </span>
          ) : null}
        </span>
      ),
    },
  ], []);

  const filtered = !!(dq || method);
  const total = data?.sums?.amount ?? 0;
  const count = data?.total ?? 0;

  return (
    <Page>
      <PageHeader
        title="Paiements"
        count={filtered ? undefined : data?.total}
        filters={
          <>
            <SearchInput value={q} onChange={setQ} placeholder="Client, référence, facture…" />
            <Select size="sm" value={method} onChange={(v) => setMethod(v as PaymentMethod | "")} placeholder="Tous les modes" options={METHOD_OPTIONS} />
          </>
        }
        actions={<Button variant="primary" icon={Plus} onClick={() => setCreating(true)}>Enregistrer un paiement</Button>}
      />
      <PageBody flush>
        {isError && !data ? (
          <EmptyState icon={Wallet} title="Paiements indisponibles" description="L'API ne répond pas. Vérifiez que le serveur tourne sur le port 4000." action={<Button size="sm" onClick={() => refetch()}>Réessayer</Button>} />
        ) : (
          <DataTable
            columns={columns}
            rows={rows}
            server={{ list, total: data?.total }}
            loading={isLoading}
            getRowId={(p) => p.id}
            footer={rows ? <>{count} paiement{count > 1 ? "s" : ""}{filtered ? " · filtrés" : ""} · Total <Money value={total} className="font-medium text-foreground" /></> : undefined}
            empty={
              filtered ? (
                <EmptyState icon={Wallet} title="Aucun paiement ne correspond" description="Modifiez la recherche ou le mode." action={<Button size="sm" onClick={() => { setQ(""); setMethod(""); }}>Effacer les filtres</Button>} />
              ) : (
                <EmptyState icon={Wallet} title="Aucun paiement" description="Les encaissements clients apparaîtront ici." action={<Button size="sm" icon={Plus} onClick={() => setCreating(true)}>Enregistrer un paiement</Button>} />
              )
            }
          />
        )}
      </PageBody>
      {creating ? <RecordPaymentPanel onClose={() => setCreating(false)} /> : null}
    </Page>
  );
}
