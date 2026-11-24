/**
 * Side panel of one client's receivables: summary, open invoices, recent payments, open disputes,
 * last reminders (late_payment events) and actions — record a payment (shared RecordPaymentPanel),
 * log a reminder inline, block / unblock, open the client page.
 */
import { useMemo, useState, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Ban, BellRing, ExternalLink, LockOpen, Wallet } from "lucide-react";
import type { ClientEvent, Id, InvoiceSummary, ReceivableRow } from "@kit/shared";
import { api } from "@/lib/api";
import { fmtMoney } from "@/lib/format";
import { PAYMENT_METHOD_LABEL } from "@/lib/labels";
import { qk, useApiMutation, useClient, useClientEvents } from "@/lib/queries";
import { cn } from "@/lib/cn";
import {
  Button, DataTable, DateLabel, EmptyState, KeyValue, Money, Mono, Section, Segmented, SidePanel, Skeleton, StatusDot, Textarea,
  type Column,
} from "@/ui";
import { CHANNEL_LABEL } from "@/pages/history/timeline";
import { RecordPaymentPanel } from "@/pages/payments/RecordPaymentPanel";
import { BUCKETS, CreditUse, MiniAging, RISK } from "./aging";

const INVOICE_LIMIT = 12;
type ReminderChannel = "phone" | "email" | "sms" | "whatsapp";
const CHANNELS: { id: ReminderChannel; label: string }[] = [
  { id: "phone", label: "Téléphone" }, { id: "email", label: "E-mail" }, { id: "sms", label: "SMS" }, { id: "whatsapp", label: "WhatsApp" },
];

const INVOICE_COLUMNS: Column<InvoiceSummary>[] = [
  { id: "number", header: "Facture", cell: (i) => <Link to={`/invoices/${i.id}`} className="hover:underline" onClick={(e) => e.stopPropagation()}><Mono>{i.number}</Mono></Link> },
  { id: "due", header: "Échéance", width: 104, cell: (i) => <DateLabel date={i.dueDate} className={i.daysOverdue > 0 ? "text-destructive" : "text-secondary-foreground"} /> },
  {
    id: "late", header: "Retard", width: 64, numeric: true,
    cell: (i) => i.daysOverdue > 0 ? <span className="text-destructive">+{i.daysOverdue} j</span> : <span className="text-muted-foreground/60">—</span>,
  },
  { id: "balance", header: "Reste dû", width: 96, numeric: true, cell: (i) => <Money value={i.balance} tone={i.daysOverdue > 0 ? "destructive" : undefined} /> },
];

export function ReceivablePanel({ clientId, row, onClose }: { clientId: Id; row?: ReceivableRow; onClose: () => void }) {
  const navigate = useNavigate();
  const [recording, setRecording] = useState(false);
  const { data: client, isLoading } = useClient(clientId);
  const { data: events } = useClientEvents(clientId, { type: "late_payment,dispute", limit: 40 });

  const openInvoices = useMemo(
    () => [...(client?.openInvoices ?? [])].filter((i) => i.balance > 0.004).sort((a, b) => a.dueDate.localeCompare(b.dueDate) || a.number.localeCompare(b.number)),
    [client],
  );
  const payments = useMemo(() => [...(client?.payments ?? [])].sort((a, b) => b.receivedAt.localeCompare(a.receivedAt)).slice(0, 5), [client]);
  const disputes = useMemo(() => (events ?? []).filter((e) => e.type === "dispute" && e.status !== "resolved"), [events]);
  const reminders = useMemo(() => (events ?? []).filter((e) => e.type === "late_payment").slice(0, 5), [events]);

  const name = row?.clientName ?? client?.name ?? "Client";
  const status = client?.status ?? row?.status;
  const blocked = status === "blocked";
  const setStatus = useApiMutation((s: "active" | "blocked") => api.clients.update(clientId, { status: s }), {
    success: (c) => (c.status === "blocked" ? `${c.name} bloqué` : `${c.name} débloqué`),
    invalidate: [qk.clients.all],
  });

  if (recording) {
    return (
      <RecordPaymentPanel
        client={{ id: clientId, name }}
        amount={row?.overdue || row?.outstanding || undefined}
        onClose={() => setRecording(false)}
      />
    );
  }

  return (
    <SidePanel
      id="receivables"
      title={
        <span className="flex items-center gap-2">
          <span className="truncate">{name}</span>
          {row ? <Mono className="text-[11.5px] font-normal text-muted-foreground">{row.clientCode}</Mono> : null}
        </span>
      }
      subtitle={row ? `${row.salesRep || "—"} · ${row.zone || "—"} · ${row.paymentTermsDays ? `${row.paymentTermsDays} j` : "comptant"}` : undefined}
      onClose={onClose}
      footer={
        <>
          <Button size="sm" variant="ghost" icon={ExternalLink} onClick={() => navigate(`/clients/${clientId}`)} className="mr-auto">Fiche client</Button>
          <Button
            size="sm"
            variant={blocked ? "default" : "danger"}
            icon={blocked ? LockOpen : Ban}
            loading={setStatus.isPending}
            disabled={!status}
            onClick={() => setStatus.mutate(blocked ? "active" : "blocked")}
          >
            {blocked ? "Débloquer" : "Bloquer"}
          </Button>
          <Button size="sm" variant="primary" icon={Wallet} onClick={() => setRecording(true)}>Enregistrer un paiement</Button>
        </>
      }
    >
      <div className="flex flex-col gap-6">
        {/* Summary */}
        {row ? (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-3 divide-x divide-border rounded-[6px] border border-border">
              <Figure label="Encours"><Money value={row.outstanding} /></Figure>
              <Figure label="Échu"><Money value={row.overdue} zeroMuted tone={row.overdue > 0 ? "destructive" : undefined} /></Figure>
              <Figure label="Risque"><StatusDot tone={RISK[row.risk].tone} label={RISK[row.risk].label} /></Figure>
            </div>
            <div className="flex flex-col gap-1.5">
              <MiniAging buckets={row.buckets} className="h-2" />
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[11.5px] text-muted-foreground">
                {BUCKETS.filter((b) => row.buckets[b.id] > 0).map((b) => (
                  <span key={b.id} className="flex items-center gap-1">
                    <span className={cn("h-1.5 w-1.5 rounded-[1px]", b.dot)} />{b.label} <Money value={row.buckets[b.id]} compact className="text-foreground" />
                  </span>
                ))}
              </div>
            </div>
            <KeyValue
              labelWidth={150}
              items={[
                { label: "Statut", value: status ? <StatusDot kind="client" value={status} /> : "—" },
                { label: "Plafond", value: row.creditLimit ? <span className="flex items-center gap-3"><Money value={row.creditLimit} compact /><CreditUse row={row} className="w-40" /></span> : "Sans plafond" },
                { label: "Plus vieille échéance", value: row.oldestDueDate ? <span className={row.maxDaysOverdue > 0 ? "text-destructive" : undefined}><DateLabel date={row.oldestDueDate} />{row.maxDaysOverdue > 0 ? ` · +${row.maxDaysOverdue} j` : ""}</span> : "—" },
                { label: "Délai moyen de paiement", value: row.avgDaysToPay != null ? `${row.avgDaysToPay} j (conditions ${row.paymentTermsDays} j)` : "—" },
                { label: "Dernier paiement", value: row.lastPaymentAt ? <span><DateLabel date={row.lastPaymentAt} /> · <Money value={row.lastPaymentAmount} /></span> : "—" },
                { label: "Dernière relance", value: row.lastReminderAt ? <DateLabel date={row.lastReminderAt} /> : "Jamais" },
              ]}
            />
          </div>
        ) : isLoading ? <Skeleton className="h-24 w-full" /> : null}

        {/* Reminder (inline) */}
        <ReminderForm clientId={clientId} overdue={row?.overdue ?? 0} overdueCount={openInvoices.filter((i) => i.daysOverdue > 0).length} />

        {/* Open invoices */}
        <Section
          title="Factures ouvertes"
          count={client ? openInvoices.length : undefined}
          actions={openInvoices.length > INVOICE_LIMIT ? <Link to={`/clients/${clientId}`} className="text-[12px] text-primary hover:underline">Tout voir</Link> : undefined}
        >
          <DataTable
            inset
            paginate={false}
            columns={INVOICE_COLUMNS}
            rows={client ? openInvoices.slice(0, INVOICE_LIMIT) : undefined}
            loading={isLoading}
            getRowId={(i) => i.id}
            onRowClick={(i) => navigate(`/invoices/${i.id}`)}
            empty={<EmptyState compact title="Aucune facture ouverte" />}
            footer={openInvoices.length > INVOICE_LIMIT ? `+ ${openInvoices.length - INVOICE_LIMIT} autres factures · ${fmtMoney(openInvoices.slice(INVOICE_LIMIT).reduce((s, i) => s + i.balance, 0))}` : undefined}
          />
        </Section>

        {/* Recent payments */}
        <Section title="Paiements récents" count={client ? client.payments.length : undefined}>
          {!client ? <Skeleton className="h-16 w-full" /> : payments.length === 0 ? (
            <p className="text-[12.5px] text-muted-foreground">Aucun paiement enregistré.</p>
          ) : (
            <ul className="divide-y divide-border rounded-[6px] border border-border">
              {payments.map((p) => (
                <li key={p.id} className="flex h-[34px] items-center gap-3 px-3 text-[13px]">
                  <DateLabel date={p.receivedAt} className="w-24 shrink-0 text-secondary-foreground" />
                  <span className="min-w-0 flex-1 truncate text-muted-foreground">{PAYMENT_METHOD_LABEL[p.method] ?? p.method}{p.reference ? ` · ${p.reference}` : ""}</span>
                  <Money value={p.amount} className="font-medium" />
                </li>
              ))}
            </ul>
          )}
        </Section>

        {/* Open disputes */}
        <Section title="Litiges ouverts" count={events ? disputes.length : undefined}>
          {!events ? <Skeleton className="h-10 w-full" /> : disputes.length === 0 ? (
            <p className="text-[12.5px] text-muted-foreground">Aucun litige ouvert.</p>
          ) : <EventList events={disputes} />}
        </Section>

        {/* Reminders */}
        <Section title="Dernières relances" count={events ? reminders.length : undefined}>
          {!events ? <Skeleton className="h-10 w-full" /> : reminders.length === 0 ? (
            <p className="text-[12.5px] text-muted-foreground">Aucune relance enregistrée.</p>
          ) : <EventList events={reminders} />}
        </Section>
      </div>
    </SidePanel>
  );
}

function Figure({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5 px-3 py-2">
      <span className="text-[11.5px] text-muted-foreground">{label}</span>
      <span className="truncate text-[14px] font-semibold">{children}</span>
    </div>
  );
}

function EventList({ events }: { events: ClientEvent[] }) {
  return (
    <ul className="flex flex-col divide-y divide-border rounded-[6px] border border-border">
      {events.map((e) => (
        <li key={e.id} className="flex flex-col gap-0.5 px-3 py-2">
          <div className="flex items-baseline gap-2">
            <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{e.title}</span>
            {e.amount ? <Money value={e.amount} className="text-[12px] text-muted-foreground" /> : null}
          </div>
          <div className="flex flex-wrap items-center gap-x-1.5 text-[11.5px] text-muted-foreground">
            <DateLabel date={e.at} />
            {e.channel ? <><span>·</span><span>{CHANNEL_LABEL[e.channel] ?? e.channel}</span></> : null}
            {e.author ? <><span>·</span><span>{e.author}</span></> : null}
            {e.type === "dispute" && e.severity ? <><span>·</span><span>{e.severity === "high" ? "Haute" : e.severity === "medium" ? "Moyenne" : "Faible"}</span></> : null}
          </div>
          {e.description ? <p className="line-clamp-2 text-[12px] text-secondary-foreground">{e.description}</p> : null}
        </li>
      ))}
    </ul>
  );
}

function ReminderForm({ clientId, overdue, overdueCount }: { clientId: Id; overdue: number; overdueCount: number }) {
  const [channel, setChannel] = useState<ReminderChannel>("phone");
  const [note, setNote] = useState("");
  const create = useApiMutation(
    () => api.clientEvents.create(clientId, {
      type: "late_payment",
      title: overdueCount > 0
        ? `Relance : ${overdueCount} facture${overdueCount > 1 ? "s" : ""} échue${overdueCount > 1 ? "s" : ""} (${fmtMoney(overdue)})`
        : "Relance paiement",
      channel,
      description: note.trim() || `Relance ${CHANNEL_LABEL[channel].toLowerCase()} pour le règlement des factures échues.`,
      amount: overdue > 0 ? Math.round(overdue * 100) / 100 : undefined,
      author: "Moi",
    }),
    { success: "Relance enregistrée", invalidate: [qk.clients.all, qk.history.all], onSuccess: () => setNote("") },
  );
  return (
    <Section title="Relancer">
      <form
        className="flex flex-col gap-2"
        onSubmit={(e) => { e.preventDefault(); create.mutate(undefined); }}
      >
        <Segmented value={channel} onChange={setChannel} options={CHANNELS} className="self-start" />
        <Textarea
          rows={2}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Ce qui a été dit, promesse de paiement…"
          onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); create.mutate(undefined); } }}
        />
        <div className="flex items-center gap-2">
          <span className="text-[11.5px] text-muted-foreground">Ajouté à l'historique du client</span>
          <Button size="sm" type="submit" icon={BellRing} loading={create.isPending} className="ml-auto">Enregistrer la relance</Button>
        </div>
      </form>
    </Section>
  );
}
