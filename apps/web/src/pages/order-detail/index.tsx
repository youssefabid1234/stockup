/** Commande — shared document editor (features/document) for a sale: lifecycle actions, KPI strip, warnings
 *  (confirm warnings kept until the next action), editable lines, note; side column = client, usual basket, invoice, route. */
import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Ban, CheckCircle2, FileText, PackageCheck, ShoppingCart, Truck } from "lucide-react";
import type { Id, OrderDetail, ProductSummary, Warning } from "@kit/shared";
import { api } from "@/lib/api";
import { qk, useApiMutation, useOrder, useProducts } from "@/lib/queries";
import { Button, DateLabel, Page, PageBody, PageHeader, StatusDot } from "@/ui";
import { DocumentKpis, DocumentLayout, DocumentNote, DocumentNotFound, DocumentSkeleton, UsualBasket, useArm, WarningList } from "@/features/document/blocks";
import { LinesTable } from "@/features/document/lines";
import { orderToDoc } from "@/features/document/model";
import { ClientCard } from "@/features/document/partner";
import { SourceLabel } from "../orders/source";
import { AlternativesPanel } from "./alternatives";
import { InvoiceSection, RouteSection } from "./aside";

export default function OrderDetailPage() {
  const { id = "" } = useParams();
  const { data: o, isLoading, isError } = useOrder(id);
  if (isLoading) return <DocumentSkeleton kind="sale" />;
  if (isError || !o) return <DocumentNotFound kind="sale" id={id} icon={ShoppingCart} />;
  return <OrderView key={o.id} order={o} />;
}

function OrderView({ order }: { order: OrderDetail }) {
  const { data: productList } = useProducts();
  const products = useMemo(() => new Map<Id, ProductSummary>((productList ?? []).map((p) => [p.id, p])), [productList]);
  const [altLineId, setAltLineId] = useState<Id | null>(null);
  const altLine = order.lines.find((l) => l.id === altLineId);
  const [confirmWarnings, setConfirmWarnings] = useState<Warning[] | null>(null);
  const doc = orderToDoc(order);

  // Warnings: live ones on the order + what confirm returned (kept until the next action).
  const warnings = useMemo(() => {
    const seen = new Set<string>();
    return [...(confirmWarnings ?? []), ...order.warnings].filter((w) => (seen.has(w.message) ? false : (seen.add(w.message), true)));
  }, [order.warnings, confirmWarnings]);

  return (
    <Page>
      <PageHeader
        breadcrumb={[{ label: "Commandes", to: "/orders" }]}
        title={<span className="font-mono text-[13.5px]">{order.number}</span>}
        meta={<><StatusDot kind="order" value={order.status} /><SourceLabel source={order.source} /></>}
        actions={<LifecycleActions order={order} onConfirmed={setConfirmWarnings} />}
      />
      <PageBody flush>
        <DocumentLayout
          kpis={
            <DocumentKpis
              doc={doc}
              products={products}
              partnerHint={<>{order.client.zone || "—"}{order.client.status === "blocked" ? <span className="ml-1.5 text-destructive">· bloqué</span> : null}</>}
              dateHint={doc.headerEditable ? undefined : order.deliveredAt ? <>Livrée <DateLabel date={order.deliveredAt} format="datetime" /></> : undefined}
              createdHint={<>{order.createdBy}{order.confirmedAt ? <> · confirmée <DateLabel date={order.confirmedAt} format="relative" /></> : null}</>}
            />
          }
          main={<>
            {order.status !== "cancelled" ? (
              <WarningList warnings={warnings} note={confirmWarnings?.length ? "retour de la confirmation" : undefined} onDismiss={confirmWarnings ? () => setConfirmWarnings(null) : undefined} />
            ) : null}
            <LinesTable doc={doc} products={products} onAlternatives={(l) => setAltLineId(l.id)} />
            <DocumentNote doc={doc} />
          </>}
          aside={<>
            <ClientCard client={order.client} />
            <UsualBasket doc={doc} />
            <InvoiceSection order={order} />
            <RouteSection order={order} />
          </>}
        />
      </PageBody>
      {altLine ? <AlternativesPanel order={order} line={altLine} onClose={() => setAltLineId(null)} /> : null}
    </Page>
  );
}

// ── Lifecycle: Annuler · Livrer · Confirmer / Préparer / Livrer / Facturer ──
function LifecycleActions({ order, onConfirmed }: { order: OrderDetail; onConfirmed: (w: Warning[] | null) => void }) {
  const navigate = useNavigate();
  const inv = [qk.orders.all, qk.dashboard, qk.stock.all, qk.products.all, qk.clients.all, qk.routeRuns.all, qk.invoices.all];
  const confirm = useApiMutation(api.orders.confirm, {
    success: (d) => `Commande ${d.number} confirmée`, invalidate: inv,
    onSuccess: (d) => onConfirmed(d.warnings.length ? d.warnings : null),
  });
  const prepare = useApiMutation((id: Id) => api.orders.prepare(id), { success: "Commande préparée", invalidate: inv, onSuccess: () => onConfirmed(null) });
  const deliver = useApiMutation(api.orders.deliver, { success: "Commande livrée", invalidate: inv, onSuccess: () => onConfirmed(null) });
  const invoice = useApiMutation(api.orders.invoice, { success: (i) => `Facture ${i.number} émise`, invalidate: inv });
  const cancel = useApiMutation(api.orders.cancel, { success: "Commande annulée", invalidate: inv, onSuccess: () => onConfirmed(null) });
  const [armCancel, setArmCancel] = useArm();

  const busy = confirm.isPending || prepare.isPending || deliver.isPending || invoice.isPending || cancel.isPending;
  const s = order.status;
  const empty = order.lines.length === 0;

  return (
    <>
      {s === "draft" || s === "confirmed" ? (
        <Button variant="danger" icon={Ban} disabled={busy && !cancel.isPending} loading={cancel.isPending}
          onClick={() => (armCancel ? cancel.mutate(order.id) : setArmCancel(true))}>
          {armCancel ? "Confirmer l'annulation" : "Annuler"}
        </Button>
      ) : null}
      {s === "confirmed" ? (
        <Button icon={Truck} disabled={busy} loading={deliver.isPending} onClick={() => deliver.mutate(order.id)}>Livrer</Button>
      ) : null}
      {s === "draft" ? (
        <Button variant="primary" icon={CheckCircle2} disabled={busy || empty} title={empty ? "Ajoutez au moins une ligne" : undefined}
          loading={confirm.isPending} onClick={() => confirm.mutate(order.id)}>Confirmer</Button>
      ) : null}
      {s === "confirmed" ? (
        <Button variant="primary" icon={PackageCheck} disabled={busy} loading={prepare.isPending} onClick={() => prepare.mutate(order.id)}>Préparer</Button>
      ) : null}
      {s === "prepared" ? (
        <Button variant="primary" icon={Truck} disabled={busy} loading={deliver.isPending} onClick={() => deliver.mutate(order.id)}>Livrer</Button>
      ) : null}
      {s === "delivered" ? (
        <Button variant="primary" icon={FileText} disabled={busy} loading={invoice.isPending} onClick={() => invoice.mutate(order.id)}>Facturer</Button>
      ) : null}
      {s === "invoiced" && order.invoice ? (
        <Button icon={FileText} onClick={() => navigate(`/invoices/${order.invoice!.id}`)}>Voir la facture</Button>
      ) : null}
    </>
  );
}
