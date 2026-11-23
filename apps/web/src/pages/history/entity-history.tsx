/**
 * "Historique" tab of the client and supplier detail pages: stats line, open issues on top (inline "Marquer résolu"),
 * full timeline (GET /clients/:id/events, /suppliers/:id/events), and the "Nouvel événement" side panel.
 * Also a compact "Historique récent" block for the overview aside.
 */
import { useMemo } from "react";
import { History } from "lucide-react";
import type { ClientDetail, Id, SupplierDetail } from "@kit/shared";
import { api } from "@/lib/api";
import { fmtDate } from "@/lib/format";
import { qk, useApiMutation, useClientEvents, useInvoices, useOrders, useSupplierEvents } from "@/lib/queries";
import { Button, Dot, Section, StatusDot } from "@/ui";
import {
  EVENT_TYPE_LABEL, EventItem, useProductNames, EventStatsLine, EventTimeline, NewEventPanel, eventTone, type EventKind, type NewEventBody,
  type TimelineEvent, type TimelineRefs,
} from "./timeline";

// ── Resolve / create mutations ──
function useResolve(kind: EventKind) {
  return useApiMutation(
    ({ ev, resolution }: { ev: TimelineEvent; resolution: string }): Promise<unknown> =>
      kind === "client"
        ? api.clientEvents.update(ev.id, { status: "resolved", ...(resolution ? { resolution } : {}) })
        : api.supplierEvents.update(ev.id, { status: "resolved", ...(resolution ? { resolution } : {}) }),
    { success: "Événement résolu", invalidate: [kind === "client" ? qk.clients.all : qk.suppliers.all, qk.history.all] },
  );
}

export function useCreateEvent(kind: EventKind, entityId: Id, onDone: () => void) {
  return useApiMutation(
    (body: NewEventBody): Promise<unknown> =>
      kind === "client" ? api.clientEvents.create(entityId, body as never) : api.supplierEvents.create(entityId, body as never),
    { success: "Événement ajouté à l'historique", invalidate: [kind === "client" ? qk.clients.all : qk.suppliers.all, qk.history.all], onSuccess: onDone },
  );
}

function HistoryBody({ kind, events, loading, stats, refs }: {
  kind: EventKind;
  events: TimelineEvent[] | undefined;
  loading: boolean;
  stats: Parameters<typeof EventStatsLine>[0]["stats"];
  refs: TimelineRefs;
}) {
  const resolve = useResolve(kind);
  const onResolve = (ev: TimelineEvent, resolution: string) => resolve.mutate({ ev, resolution });
  const resolvingId = resolve.isPending ? resolve.variables?.ev.id : undefined;
  const open = useMemo(() => (events ?? []).filter((e) => e.status === "open"), [events]);
  const productName = useProductNames();

  return (
    <div className="flex flex-col gap-5 px-5 py-4">
      <EventStatsLine kind={kind} stats={stats} />
      {open.length ? (
        <Section title="À traiter" count={open.length}>
          <ol className="flex flex-col gap-2">
            {open.map((e) => (
              <EventItem key={e.id} kind={kind} ev={e} refs={refs} productName={productName} onResolve={onResolve} resolving={resolvingId === e.id} highlight />
            ))}
          </ol>
        </Section>
      ) : null}
      <Section title="Historique complet" count={events?.length}>
        <EventTimeline kind={kind} events={events} loading={loading} refs={refs} onResolve={onResolve} resolvingId={resolvingId} />
      </Section>
    </div>
  );
}

// ── Client ──
export function useClientRefs(clientId: Id) {
  // The 60 latest of each (link options); events already carry the number of what they link to.
  const { data: orders } = useOrders({ clientId, limit: 60 });
  const { data: invoices } = useInvoices({ clientId, limit: 60 });
  return useMemo(() => {
    const o = [...(orders ?? [])].sort((a, b) => b.deliveryDate.localeCompare(a.deliveryDate));
    const i = [...(invoices ?? [])].sort((a, b) => b.issuedAt.localeCompare(a.issuedAt));
    return {
      refs: { orders: new Map(o.map((x) => [x.id, x.number])), invoices: new Map(i.map((x) => [x.id, x.number])) } as TimelineRefs,
      orderOptions: o.slice(0, 60).map((x) => ({ value: x.id, label: `${x.number} · livraison ${fmtDate(x.deliveryDate)}` })),
      invoiceOptions: i.slice(0, 60).map((x) => ({ value: x.id, label: `${x.number} · ${fmtDate(x.issuedAt)}` })),
    };
  }, [orders, invoices]);
}

export function ClientHistoryTab({ c }: { c: ClientDetail }) {
  const { data, isLoading } = useClientEvents(c.id);
  const { refs } = useClientRefs(c.id);
  return <HistoryBody kind="client" events={data} loading={isLoading} stats={c.eventStats} refs={refs} />;
}

export function ClientNewEventPanel({ c, onClose }: { c: ClientDetail; onClose: () => void }) {
  const { orderOptions, invoiceOptions } = useClientRefs(c.id);
  const create = useCreateEvent("client", c.id, onClose);
  return (
    <NewEventPanel
      kind="client"
      subtitle={c.name}
      onClose={onClose}
      onSubmit={(b) => create.mutate(b)}
      pending={create.isPending}
      links={[
        { field: "orderId", label: "Commande liée", options: orderOptions },
        { field: "invoiceId", label: "Facture liée", options: invoiceOptions },
      ]}
    />
  );
}

// ── Supplier ──
function supplierRefs(s: SupplierDetail) {
  const pos = [...s.purchaseOrders].sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return {
    refs: { purchaseOrders: new Map(pos.map((p) => [p.id, p.number])) } as TimelineRefs,
    poOptions: pos.slice(0, 60).map((p) => ({ value: p.id, label: `${p.number} · ${fmtDate(p.createdAt)}` })),
  };
}

export function SupplierHistoryTab({ s }: { s: SupplierDetail }) {
  const { data, isLoading } = useSupplierEvents(s.id);
  const { refs } = useMemo(() => supplierRefs(s), [s]);
  return <HistoryBody kind="supplier" events={data} loading={isLoading} stats={s.eventStats} refs={refs} />;
}

export function SupplierNewEventPanel({ s, onClose }: { s: SupplierDetail; onClose: () => void }) {
  const { poOptions } = useMemo(() => supplierRefs(s), [s]);
  const create = useCreateEvent("supplier", s.id, onClose);
  return (
    <NewEventPanel
      kind="supplier"
      subtitle={s.name}
      onClose={onClose}
      onSubmit={(b) => create.mutate(b)}
      pending={create.isPending}
      links={[{ field: "purchaseOrderId", label: "Commande d'achat liée", options: poOptions }]}
    />
  );
}

// ── Compact block for the overview aside ──
export function RecentHistory({ kind, events, stats, onOpen }: {
  kind: EventKind;
  events: TimelineEvent[];
  stats: Parameters<typeof EventStatsLine>[0]["stats"];
  onOpen: () => void;
}) {
  const shown = [...events.filter((e) => e.status === "open"), ...events.filter((e) => e.status !== "open")].slice(0, 6);
  return (
    <Section
      title="Historique"
      count={stats.total}
      actions={<Button size="sm" variant="ghost" icon={History} onClick={onOpen}>Tout voir</Button>}
    >
      <EventStatsLine kind={kind} stats={stats} className="mb-2 text-[12px]" />
      {shown.length === 0 ? (
        <div className="text-[12.5px] text-muted-foreground">Aucun événement pour l'instant.</div>
      ) : (
        <ul className="flex flex-col divide-y divide-border rounded-[6px] border border-border bg-card">
          {shown.map((e) => (
            <li key={e.id}>
              <button type="button" onClick={onOpen} className="flex w-full items-start gap-2 px-3 py-2 text-left hover:bg-muted/50">
                <Dot tone={eventTone(e)} className="mt-[6px]" />
                <span className="min-w-0 flex-1">
                  <span className="line-clamp-1 text-[12.5px] font-medium">{e.title}</span>
                  <span className="block text-[11.5px] text-muted-foreground">
                    {EVENT_TYPE_LABEL[e.type]} · {fmtDate(e.at)} {e.at.slice(0, 4)}
                  </span>
                </span>
                {e.status === "open" ? <StatusDot tone="warning" label="Ouvert" className="shrink-0 text-[11.5px]" /> : null}
              </button>
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
