/** Facture — the invoice as a clean document (seller/buyer, lines with VAT, totals) + side column
 *  (status, due date, linked orders, allocated payments, "Enregistrer un paiement"). */
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { FileText, Wallet } from "lucide-react";
import type { InvoiceDetail } from "@kit/shared";
import { CLIENT_TYPE_LABEL, PAYMENT_METHOD_LABEL } from "@/lib/labels";
import { fmtNumber } from "@/lib/format";
import { useInvoice, useMeta, useOrders } from "@/lib/queries";
import { cn } from "@/lib/cn";
import {
  Button, DateLabel, EmptyState, KeyValue, Money, Mono, Page, PageBody, PageHeader, SECTION_LABEL, Section, Skeleton,
  StatusDot,
} from "@/ui";
import { RecordPaymentPanel } from "../payments/RecordPaymentPanel";

const pctVat = new Intl.NumberFormat("fr-FR", { style: "percent", maximumFractionDigits: 1 });
const OPEN = new Set(["issued", "partially_paid", "overdue"]);
const CRUMB = [{ label: "Factures", to: "/invoices" }];

export default function InvoiceDetailPage() {
  const { id = "" } = useParams();
  const { data: inv, isLoading, isError } = useInvoice(id);

  if (isLoading) return <DetailSkeleton />;
  if (isError || !inv) {
    return (
      <Page>
        <PageHeader breadcrumb={CRUMB} title={id} />
        <PageBody><EmptyState icon={FileText} title="Facture introuvable" description={`Aucune facture ne correspond à l'identifiant ${id}.`} /></PageBody>
      </Page>
    );
  }
  return <InvoiceView inv={inv} />;
}

function InvoiceView({ inv }: { inv: InvoiceDetail }) {
  const [paying, setPaying] = useState(false);
  const isOpen = OPEN.has(inv.status) && inv.balance > 0.004;

  return (
    <Page>
      <PageHeader
        breadcrumb={CRUMB}
        title={<Mono className="text-[14px] font-semibold text-foreground">{inv.number}</Mono>}
        meta={<><StatusDot kind="invoice" value={inv.status} /><span className="text-[12.5px] text-muted-foreground">{inv.clientName}</span></>}
        actions={isOpen ? <Button variant="primary" icon={Wallet} onClick={() => setPaying(true)}>Enregistrer un paiement</Button> : null}
      />
      <PageBody>
        <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1fr)_340px]">
          <InvoiceDocument inv={inv} />
          <aside className="flex min-w-0 flex-col gap-7">
            <Section title="Suivi">
              <KeyValue
                labelWidth={110}
                items={[
                  { label: "Statut", value: <StatusDot kind="invoice" value={inv.status} /> },
                  { label: "Émise le", value: <DateLabel date={inv.issuedAt} format="long" /> },
                  {
                    label: "Échéance",
                    value: (
                      <span className={inv.daysOverdue > 0 ? "text-destructive" : undefined}>
                        <DateLabel date={inv.dueDate} format="long" />
                        {inv.daysOverdue > 0 ? <span className="num ml-1.5 text-[12px]">+{inv.daysOverdue} j</span> : null}
                      </span>
                    ),
                  },
                  { label: "Total TTC", value: <Money value={inv.totalTtc} /> },
                  { label: "Payé", value: <Money value={inv.amountPaid} zeroMuted /> },
                  { label: "Reste dû", value: <Money value={inv.balance} zeroMuted className="font-semibold" tone={inv.daysOverdue > 0 ? "destructive" : undefined} /> },
                ]}
              />
              {inv.totalTtc > 0 ? <PaidBar paid={inv.amountPaid} total={inv.totalTtc} /> : null}
            </Section>
            <LinkedOrders inv={inv} />
            <Payments inv={inv} onPay={isOpen ? () => setPaying(true) : undefined} />
          </aside>
        </div>
      </PageBody>
      {paying ? (
        <RecordPaymentPanel
          onClose={() => setPaying(false)}
          client={{ id: inv.clientId, name: inv.clientName }}
          amount={inv.balance}
          invoiceId={inv.id}
        />
      ) : null}
    </Page>
  );
}

function PaidBar({ paid, total }: { paid: number; total: number }) {
  const r = Math.max(0, Math.min(1, paid / total));
  return (
    <div className="mt-3 h-1 overflow-hidden rounded-full bg-muted">
      <div className={cn("h-full rounded-full", r >= 0.999 ? "bg-success" : "bg-warning")} style={{ width: `${r * 100}%` }} />
    </div>
  );
}

// ── The document ──
function InvoiceDocument({ inv }: { inv: InvoiceDetail }) {
  const { data: meta } = useMeta();
  const c = inv.client;
  const vatGroups = useMemo(() => {
    const m = new Map<number, number>();
    inv.lines.forEach((l) => m.set(l.vatRate, (m.get(l.vatRate) ?? 0) + l.totalHt));
    return [...m.entries()].sort((a, b) => a[0] - b[0]);
  }, [inv.lines]);

  return (
    <article className="min-w-0 rounded-[6px] border border-border bg-card">
      <div className="flex flex-wrap items-start justify-between gap-6 border-b border-border px-8 py-7">
        <div>
          <div className="text-[18px] font-semibold tracking-[-0.01em]">Facture</div>
          <Mono className="mt-1 block text-[12.5px]">{inv.number}</Mono>
        </div>
        <div className="grid grid-cols-[auto_auto] gap-x-4 gap-y-1 text-[12.5px]">
          <span className="text-muted-foreground">Date d'émission</span><DateLabel date={inv.issuedAt} format="long" className="text-right" />
          <span className="text-muted-foreground">Échéance</span><DateLabel date={inv.dueDate} format="long" className={cn("text-right", inv.daysOverdue > 0 && "text-destructive")} />
          <span className="text-muted-foreground">Conditions</span>
          <span className="text-right">{c.paymentTermsDays ? `${c.paymentTermsDays} jours` : "Comptant"}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 border-b border-border px-8 py-6 sm:grid-cols-2">
        <div>
          <div className={SECTION_LABEL}>Vendeur</div>
          <div className="mt-2 font-semibold">{meta?.company ?? "—"}</div>
        </div>
        <div>
          <div className={SECTION_LABEL}>Facturé à</div>
          <Link to={`/clients/${c.id}`} className="mt-2 block font-semibold hover:underline">{c.name}</Link>
          <div className="mt-0.5 text-[12.5px] leading-[18px] text-secondary-foreground">
            {c.address ? <>{c.address}<br /></> : null}
            {c.city}
          </div>
          <div className="mt-1 text-[12px] text-muted-foreground">
            Client <Mono className="text-muted-foreground">{c.code}</Mono> · {CLIENT_TYPE_LABEL[c.type] ?? c.type}
          </div>
        </div>
      </div>

      <div className="px-8 py-5">
        <table className="w-full border-separate border-spacing-0 text-[13px]">
          <thead>
            <tr className="text-[12px] text-muted-foreground">
              <th className="h-8 border-b border-border pr-3 text-left font-medium">Désignation</th>
              <th className="h-8 w-[90px] border-b border-border px-3 text-right font-medium">Qté</th>
              <th className="h-8 w-[110px] border-b border-border px-3 text-right font-medium">PU HT</th>
              <th className="h-8 w-[70px] border-b border-border px-3 text-right font-medium">TVA</th>
              <th className="h-8 w-[120px] border-b border-border pl-3 text-right font-medium">Total HT</th>
            </tr>
          </thead>
          <tbody>
            {inv.lines.map((l, i) => (
              <tr key={`${l.productId}-${i}`} className="h-[34px]">
                <td className="border-b border-border pr-3">
                  {l.productId ? <Link to={`/products/${l.productId}`} className="hover:underline">{l.label}</Link> : l.label}
                </td>
                <td className="num border-b border-border px-3 text-right">{fmtNumber(l.qty)}</td>
                <td className="border-b border-border px-3 text-right"><Money value={l.unitPrice} /></td>
                <td className="num border-b border-border px-3 text-right text-muted-foreground">{pctVat.format(l.vatRate)}</td>
                <td className="border-b border-border pl-3 text-right"><Money value={l.totalHt} /></td>
              </tr>
            ))}
            {inv.lines.length === 0 ? (
              <tr><td colSpan={5} className="py-4 text-center text-[12.5px] text-muted-foreground">Aucune ligne.</td></tr>
            ) : null}
          </tbody>
        </table>

        <div className="mt-5 flex justify-end">
          <dl className="grid w-full max-w-[320px] grid-cols-[1fr_auto] gap-x-6 gap-y-1.5 text-[13px]">
            <dt className="text-muted-foreground">Total HT</dt><dd className="text-right"><Money value={inv.totalHt} /></dd>
            {vatGroups.map(([rate, base]) => (
              <div key={rate} className="contents">
                <dt className="text-muted-foreground">TVA {pctVat.format(rate)} <span className="text-[11.5px]">sur <Money value={base} /></span></dt>
                <dd className="text-right"><Money value={base * rate} /></dd>
              </div>
            ))}
            {vatGroups.length > 1 ? (<><dt className="text-muted-foreground">Total TVA</dt><dd className="text-right"><Money value={inv.totalVat} /></dd></>) : null}
            <dt className="mt-1.5 border-t border-border pt-2 font-semibold">Total TTC</dt>
            <dd className="mt-1.5 border-t border-border pt-2 text-right"><Money value={inv.totalTtc} className="text-[15px] font-semibold" /></dd>
            {inv.amountPaid > 0 ? (
              <>
                <dt className="text-muted-foreground">Déjà réglé</dt><dd className="text-right"><Money value={-inv.amountPaid} className="text-muted-foreground" /></dd>
                <dt className="font-medium">Net à payer</dt>
                <dd className="text-right"><Money value={inv.balance} className="font-semibold" tone={inv.daysOverdue > 0 ? "destructive" : undefined} /></dd>
              </>
            ) : null}
          </dl>
        </div>
      </div>

      <div className="border-t border-border px-8 py-4 text-[11.5px] leading-[17px] text-muted-foreground">
        Paiement à réception{c.paymentTermsDays ? ` ou sous ${c.paymentTermsDays} jours` : ""}. En cas de retard, pénalités au taux légal
        et indemnité forfaitaire de 40 € pour frais de recouvrement.
      </div>
    </article>
  );
}

// ── Side sections ──
function LinkedOrders({ inv }: { inv: InvoiceDetail }) {
  const { data: orders } = useOrders({ ids: inv.orderIds.join(","), limit: inv.orderIds.length || 1 }, inv.orderIds.length > 0);
  const byId = useMemo(() => new Map((orders ?? []).map((o) => [o.id, o])), [orders]);
  return (
    <Section title="Commandes liées" count={inv.orderIds.length}>
      {inv.orderIds.length === 0 ? (
        <div className="text-[12.5px] text-muted-foreground">Aucune commande liée.</div>
      ) : (
        <ul className="divide-y divide-border rounded-[6px] border border-border bg-card">
          {inv.orderIds.map((oid) => {
            const o = byId.get(oid);
            return (
              <li key={oid}>
                <Link to={`/orders/${oid}`} className="flex h-[34px] items-center gap-2 px-3 hover:bg-muted/60">
                  <Mono>{o?.number ?? oid}</Mono>
                  {o ? <DateLabel date={o.deliveryDate} className="text-[12px] text-muted-foreground" /> : null}
                  {o ? <Money value={o.totalHt} className="ml-auto text-[12.5px]" /> : null}
                </Link>
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

function Payments({ inv, onPay }: { inv: InvoiceDetail; onPay?: () => void }) {
  const rows = [...inv.payments].sort((a, b) => b.receivedAt.localeCompare(a.receivedAt));
  return (
    <Section title="Paiements imputés" count={rows.length} actions={onPay ? <Button size="sm" variant="ghost" icon={Wallet} onClick={onPay}>Enregistrer</Button> : null}>
      {rows.length === 0 ? (
        <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-border px-3 py-3 text-[12.5px] text-muted-foreground">
          <Wallet size={14} strokeWidth={1.75} />Aucun paiement imputé sur cette facture.
        </div>
      ) : (
        <ul className="divide-y divide-border rounded-[6px] border border-border bg-card">
          {rows.map((p) => {
            const a = p.allocations.find((x) => x.invoiceId === inv.id);
            return (
              <li key={p.id} className="flex items-start gap-2 px-3 py-2">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <DateLabel date={p.receivedAt} />
                    <span className="text-muted-foreground">· {PAYMENT_METHOD_LABEL[p.method] ?? p.method}</span>
                  </div>
                  {p.reference ? <Mono className="text-[11.5px] text-muted-foreground">{p.reference}</Mono> : null}
                </div>
                <div className="text-right">
                  <Money value={a?.amount ?? p.amount} className="font-medium" />
                  {a && Math.abs(a.amount - p.amount) > 0.004 ? (
                    <div className="text-[11.5px] text-muted-foreground">sur <Money value={p.amount} /></div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </Section>
  );
}

function DetailSkeleton() {
  return (
    <Page>
      <PageHeader breadcrumb={CRUMB} title={<Skeleton className="h-4 w-40" />} />
      <PageBody>
        <div className="grid grid-cols-1 gap-8 xl:grid-cols-[minmax(0,1fr)_340px]">
          <div className="flex flex-col gap-3 rounded-[6px] border border-border p-8">{Array.from({ length: 9 }).map((_, i) => <Skeleton key={i} className="h-6 w-full" />)}</div>
          <div className="flex flex-col gap-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-4 w-full" />)}</div>
        </div>
      </PageBody>
    </Page>
  );
}
