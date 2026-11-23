/**
 * "Enregistrer un paiement" side panel — shared by Paiements and the invoice detail page.
 *  - client search (or a fixed client when opened from an invoice),
 *  - amount / method / date / reference,
 *  - optional manual allocation over the client's open invoices (otherwise the API allocates oldest-first),
 *  - after save, the panel shows the resulting allocation returned by the API.
 */
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, Search, X } from "lucide-react";
import type { Id, InvoiceSummary, PaymentMethod, PaymentSummary } from "@kit/shared";
import { api, LIST_MAX } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import { PAYMENT_METHOD_LABEL } from "@/lib/labels";
import { qk, useApiMutation, useClients, useInvoices, useMeta } from "@/lib/queries";
import { useDebounced } from "@/lib/url-state";
import { cn } from "@/lib/cn";
import {
  Button, DateLabel, DatePicker, Field, IconButton, Input, Money, Mono, Section, Segmented, Select, SidePanel, Skeleton, StatusDot,
} from "@/ui";

const PAST_PRESETS = [{ label: "Aujourd'hui", days: 0 }, { label: "Hier", days: -1 }, { label: "−7 j", days: -7 }];
const METHOD_OPTIONS = Object.entries(PAYMENT_METHOD_LABEL).map(([value, label]) => ({ value, label }));
const OPEN_STATUSES = new Set(["issued", "partially_paid", "overdue"]);
const round2 = (n: number) => Math.round(n * 100) / 100;
const parseAmount = (s: string) => {
  const n = Number(s.replace(/\s/g, "").replace(",", "."));
  return Number.isFinite(n) ? n : NaN;
};
const toInput = (n: number) => String(round2(n)).replace(".", ",");

export interface RecordPaymentPanelProps {
  onClose: () => void;
  /** fixed client (opened from an invoice) */
  client?: { id: Id; name: string };
  /** prefilled amount (e.g. the invoice balance) */
  amount?: number;
  /** invoice the payment is primarily for: preselected in manual allocation */
  invoiceId?: Id;
}

export function RecordPaymentPanel({ onClose, client: fixedClient, amount: initialAmount, invoiceId }: RecordPaymentPanelProps) {
  const { data: meta } = useMeta();
  const [client, setClient] = useState<{ id: Id; name: string } | null>(fixedClient ?? null);
  const [amount, setAmount] = useState(initialAmount ? toInput(initialAmount) : "");
  const [method, setMethod] = useState<PaymentMethod>("transfer");
  const [date, setDate] = useState("");
  const [reference, setReference] = useState("");
  const [mode, setMode] = useState<"auto" | "manual">(invoiceId ? "manual" : "auto");
  const [alloc, setAlloc] = useState<Record<Id, string>>({});
  const [allocTouched, setAllocTouched] = useState(false);
  const [result, setResult] = useState<PaymentSummary | null>(null);

  const receivedAt = date || meta?.today || "";
  const amountN = parseAmount(amount);

  // Open invoices of the chosen client only (bounded), oldest first.
  const { data: invoices, isLoading: invLoading } = useInvoices(
    client ? { clientId: client.id, status: "open", sort: "issued", order: "asc", limit: LIST_MAX } : undefined, !!client,
  );
  const open = useMemo(
    () => (client ? (invoices ?? []).filter((i) => i.clientId === client.id && OPEN_STATUSES.has(i.status) && i.balance > 0.004) : [])
      .sort((a, b) => a.issuedAt.localeCompare(b.issuedAt) || a.number.localeCompare(b.number)),
    [invoices, client],
  );
  const numberOf = useMemo(() => new Map((invoices ?? []).map((i) => [i.id, i])), [invoices]);

  // Until the user edits the allocation, the focused invoice follows the amount.
  const effectiveAlloc: Record<Id, string> = useMemo(() => {
    if (allocTouched || !invoiceId) return alloc;
    const inv = open.find((i) => i.id === invoiceId);
    if (!inv || !(amountN > 0)) return {};
    return { [invoiceId]: toInput(Math.min(amountN, inv.balance)) };
  }, [alloc, allocTouched, invoiceId, open, amountN]);

  const allocations = Object.entries(effectiveAlloc)
    .map(([id, v]) => ({ invoiceId: id, amount: round2(parseAmount(v)) }))
    .filter((a) => a.amount > 0);
  const allocated = round2(allocations.reduce((s, a) => s + a.amount, 0));
  const overBalance = allocations.some((a) => {
    const inv = open.find((i) => i.id === a.invoiceId);
    return inv ? a.amount > inv.balance + 0.004 : false;
  });
  const badNumbers = Object.values(effectiveAlloc).some((v) => v.trim() !== "" && !(parseAmount(v) >= 0));
  const manualError =
    mode !== "manual" ? null
      : badNumbers ? "Montant d'imputation invalide."
      : overBalance ? "Une imputation dépasse le reste dû de la facture."
      : amountN > 0 && allocated > amountN + 0.004 ? `Imputé ${fmtMoney(allocated)} > montant du paiement.`
      : null;

  const canSave = !!client && amountN > 0 && !manualError && !!receivedAt;

  const create = useApiMutation(api.payments.create, {
    success: (p) => `Paiement de ${fmtMoney(p.amount)} enregistré`,
    invalidate: [qk.payments.all, qk.invoices.all, qk.clients.all, qk.dashboard],
    onSuccess: (p) => setResult(p),
  });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSave || !client) return;
    create.mutate({
      clientId: client.id,
      amount: round2(amountN),
      method,
      receivedAt,
      reference: reference.trim() || undefined,
      allocations: mode === "manual" && allocations.length ? allocations : undefined,
    });
  };

  const setLine = (id: Id, v: string) => {
    setAllocTouched(true);
    setAlloc({ ...effectiveAlloc, [id]: v });
  };
  const toggleLine = (inv: InvoiceSummary, on: boolean) => {
    const remaining = Math.max(0, (amountN > 0 ? amountN : inv.balance) - allocated);
    setLine(inv.id, on ? toInput(Math.min(inv.balance, remaining || inv.balance)) : "");
  };

  if (result) {
    const total = result.allocations.reduce((s, a) => s + a.amount, 0);
    const unallocated = round2(result.amount - total);
    return (
      <SidePanel
        title="Paiement enregistré"
        subtitle={`${result.clientName} · ${PAYMENT_METHOD_LABEL[result.method]}`}
        onClose={onClose}
        footer={<Button variant="primary" onClick={onClose}>Terminer</Button>}
      >
        <div className="flex flex-col gap-5">
          <div className="flex items-start gap-2.5 rounded-[6px] border border-border bg-muted/40 px-3 py-2.5">
            <CheckCircle2 size={16} strokeWidth={1.75} className="mt-0.5 shrink-0 text-success" />
            <div className="text-[13px]">
              <Money value={result.amount} className="font-semibold" /> reçu le <DateLabel date={result.receivedAt} format="long" />
              {result.reference ? <> · réf. <Mono>{result.reference}</Mono></> : null}
            </div>
          </div>
          <Section title="Imputation" count={result.allocations.length}>
            {result.allocations.length === 0 ? (
              <div className="text-[12.5px] text-muted-foreground">Aucune facture ouverte : le paiement reste en avoir non imputé.</div>
            ) : (
              <ul className="divide-y divide-border rounded-[6px] border border-border bg-card">
                {result.allocations.map((a) => {
                  const inv = numberOf.get(a.invoiceId);
                  return (
                    <li key={a.invoiceId} className="flex h-[34px] items-center gap-2 px-3">
                      <Link to={`/invoices/${a.invoiceId}`} onClick={onClose} className="hover:underline"><Mono>{inv?.number ?? a.invoiceId}</Mono></Link>
                      {inv ? <StatusDot kind="invoice" value={inv.status} /> : null}
                      <Money value={a.amount} className="ml-auto font-medium" />
                    </li>
                  );
                })}
              </ul>
            )}
            {unallocated > 0.004 ? (
              <div className="mt-2 text-[12px] text-muted-foreground">Non imputé : <Money value={unallocated} className="text-foreground" /></div>
            ) : null}
          </Section>
        </div>
      </SidePanel>
    );
  }

  return (
    <SidePanel
      title="Enregistrer un paiement"
      subtitle={fixedClient ? fixedClient.name : "Encaissement client"}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Annuler</Button>
          <Button variant="primary" type="submit" form="record-payment" loading={create.isPending} disabled={!canSave}>Enregistrer</Button>
        </>
      }
    >
      <form id="record-payment" onSubmit={submit} className="flex flex-col gap-3.5">
        <Field label="Client">
          {client ? (
            <div className="flex h-8 items-center gap-2 rounded-[4px] border border-border bg-muted/40 px-2.5">
              <span className="truncate font-medium">{client.name}</span>
              {!fixedClient ? (
                <IconButton icon={X} size="sm" label="Changer de client" className="ml-auto" onClick={() => { setClient(null); setAlloc({}); setAllocTouched(false); }} />
              ) : null}
            </div>
          ) : (
            <ClientPicker onPick={(c) => { setClient(c); setAlloc({}); setAllocTouched(false); }} />
          )}
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Montant (€ TTC)">
            <Input inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} placeholder="0,00" className="num text-right" autoFocus={!!fixedClient} />
          </Field>
          <Field label="Mode de paiement">
            <Select value={method} onChange={(v) => setMethod(v as PaymentMethod)} options={METHOD_OPTIONS} className="w-full" />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Date de réception">
            <DatePicker value={receivedAt} onChange={setDate} presets={PAST_PRESETS} />
          </Field>
          <Field label="Référence">
            <Input value={reference} onChange={(e) => setReference(e.target.value)} placeholder="VIR 2311-042, chèque n°…" />
          </Field>
        </div>

        {client ? (
          <Section
            className="mt-2"
            title="Imputation"
            actions={
              <Segmented
                value={mode}
                onChange={setMode}
                options={[{ id: "auto", label: "Automatique" }, { id: "manual", label: "Manuelle" }]}
              />
            }
          >
            {invLoading && !invoices ? (
              <div className="flex flex-col gap-2">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-7 w-full" />)}</div>
            ) : open.length === 0 ? (
              <div className="rounded-[6px] border border-dashed border-border px-3 py-3 text-[12.5px] text-muted-foreground">
                Aucune facture ouverte pour ce client : le paiement sera enregistré sans imputation.
              </div>
            ) : mode === "auto" ? (
              <div className="text-[12.5px] text-muted-foreground">
                Le montant sera imputé sur les factures les plus anciennes d'abord ({open.length} ouverte{open.length > 1 ? "s" : ""},
                reste dû <Money value={open.reduce((s, i) => s + i.balance, 0)} className="text-foreground" />).
              </div>
            ) : (
              <>
                <ul className="divide-y divide-border rounded-[6px] border border-border bg-card">
                  {open.map((inv) => {
                    const v = effectiveAlloc[inv.id] ?? "";
                    const on = parseAmount(v) > 0;
                    return (
                      <li key={inv.id} className={cn("flex items-center gap-2.5 px-3 py-1.5", on && "bg-row-selected")}>
                        <input type="checkbox" checked={on} onChange={(e) => toggleLine(inv, e.target.checked)} className="accent-[hsl(var(--primary))]" aria-label={`Imputer ${inv.number}`} />
                        <div className="min-w-0 flex-1">
                          <Mono>{inv.number}</Mono>
                          <div className={cn("text-[11.5px]", inv.daysOverdue > 0 ? "text-destructive" : "text-muted-foreground")}>
                            Échéance <DateLabel date={inv.dueDate} />{inv.daysOverdue > 0 ? ` · +${inv.daysOverdue} j` : ""} · reste <Money value={inv.balance} />
                          </div>
                        </div>
                        <Input size="sm" inputMode="decimal" value={v} onChange={(e) => setLine(inv.id, e.target.value)} placeholder="0,00" className="num w-24 text-right" />
                      </li>
                    );
                  })}
                </ul>
                <div className="mt-2 flex items-center justify-between text-[12px]">
                  <span className={manualError ? "text-destructive" : "text-muted-foreground"}>
                    {manualError ?? (allocated === 0 ? "Aucune ligne cochée : imputation automatique." : amountN > allocated ? `Non imputé : ${fmtMoney(round2(amountN - allocated))}` : "Montant entièrement imputé.")}
                  </span>
                  <span className="text-muted-foreground">Imputé <Money value={allocated} className="font-medium text-foreground" /></span>
                </div>
              </>
            )}
          </Section>
        ) : null}
      </form>
    </SidePanel>
  );
}

function ClientPicker({ onPick }: { onPick: (c: { id: Id; name: string }) => void }) {
  const [q, setQ] = useState("");
  const dq = useDebounced(q, 150);
  const { data, isLoading } = useClients({ q: dq, limit: 8 });
  const list = (data ?? []).slice(0, 8);
  return (
    <div className="flex flex-col gap-1.5">
      <Input autoFocus leading={<Search size={13} strokeWidth={1.75} />} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher un client…" />
      <ul className="max-h-[264px] divide-y divide-border overflow-auto rounded-[6px] border border-border bg-card">
        {isLoading && !data ? (
          <li className="px-3 py-2"><Skeleton className="h-3 w-40" /></li>
        ) : list.length === 0 ? (
          <li className="px-3 py-2 text-[12.5px] text-muted-foreground">Aucun client ne correspond.</li>
        ) : (
          list.map((c) => (
            <li key={c.id}>
              <button type="button" onClick={() => onPick({ id: c.id, name: c.name })} className="flex h-[34px] w-full items-center gap-2 px-3 text-left hover:bg-muted/60">
                <span className="truncate font-medium">{c.name}</span>
                <Mono className="text-muted-foreground">{c.code}</Mono>
                {c.outstanding > 0 ? (
                  <span className="ml-auto text-[12px] text-muted-foreground">Encours <Money value={c.outstanding} tone={c.overdue > 0 ? "destructive" : undefined} /></span>
                ) : null}
              </button>
            </li>
          ))
        )}
      </ul>
    </div>
  );
}
