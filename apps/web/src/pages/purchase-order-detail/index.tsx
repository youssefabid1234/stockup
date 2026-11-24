/** Achat — shared document editor (features/document) for a purchase: Envoyer / Réceptionner (inline receive mode,
 *  partial receipts per line) / Annuler, KPI strip, warnings, editable lines with usual-price gap, expected date + note,
 *  lots received; side column = supplier, usual purchases, other orders at this supplier. */
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Ban, Boxes, Check, PackageCheck, Send, ShoppingBasket } from "lucide-react";
import type { Id, Lot, ProductSummary, PurchaseOrderDetail, PurchaseOrderSummary } from "@kit/shared";
import { api } from "@/lib/api";
import { fmtPercent, UNIT_LABEL } from "@/lib/format";
import { qk, useApiMutation, useProducts, usePurchaseOrder, useSupplier } from "@/lib/queries";
import { Badge, Button, DataTable, DateLabel, Input, Money, Mono, Page, PageBody, PageHeader, Qty, Section, StatusDot, type Column } from "@/ui";
import { ExpiryLabel, useToday } from "@/pages/stock/shared";
import { DocumentKpis, DocumentLayout, DocumentNote, DocumentNotFound, DocumentSkeleton, UsualBasket, useArm, WarningList } from "@/features/document/blocks";
import { LinesTable } from "@/features/document/lines";
import { purchaseToDoc, type DocLine } from "@/features/document/model";
import { SupplierCard } from "@/features/document/partner";

const num = (s: string) => Number(s.replace(",", "."));
const round3 = (n: number) => Math.round(n * 1000) / 1000;
const INVALIDATE = [qk.purchaseOrders.all, qk.stock.all, qk.products.all, qk.suppliers.all, qk.dashboard];

export default function PurchaseOrderDetailPage() {
  const { id = "" } = useParams();
  const { data: po, isLoading, isError } = usePurchaseOrder(id);
  if (isLoading) return <DocumentSkeleton kind="purchase" />;
  if (isError || !po) return <DocumentNotFound kind="purchase" id={id} icon={ShoppingBasket} />;
  return <PurchaseOrderView key={po.id} po={po} />;
}

function PurchaseOrderView({ po }: { po: PurchaseOrderDetail }) {
  const today = useToday();
  const { data: productList } = useProducts();
  const products = useMemo(() => new Map<Id, ProductSummary>((productList ?? []).map((p) => [p.id, p])), [productList]);
  const { data: supplier } = useSupplier(po.supplierId);
  const supplierPrices = useMemo(() => (supplier ? new Map(supplier.prices.map((p) => [p.productId, p.price])) : undefined), [supplier]);
  const doc = purchaseToDoc(po);

  const [receiving, setReceiving] = useState(false);
  const [qtys, setQtys] = useState<Record<string, string>>({});
  const [createdLotIds, setCreatedLotIds] = useState<string[]>([]);
  const [armCancel, setArmCancel] = useArm();

  const send = useApiMutation(() => api.purchaseOrders.send(po.id), { success: (d) => `${d.number} envoyée à ${d.supplier.name}`, invalidate: INVALIDATE });
  const cancel = useApiMutation(() => api.purchaseOrders.cancel(po.id), { success: (d) => `${d.number} annulée`, invalidate: INVALIDATE });
  const receive = useApiMutation(
    async (lines: { lineId: string; receivedQty: number }[]) => {
      const d = await api.purchaseOrders.receive(po.id, { lines });
      return { ...d, warnings: undefined }; // warnings stay inline; they were toasted on send
    },
    {
      success: (d) => (d.status === "received" ? "Réception complète" : "Réception partielle enregistrée"),
      invalidate: INVALIDATE,
      onSuccess: (d) => {
        const before = new Set(po.lots.map((l) => l.id));
        setCreatedLotIds(d.lots.filter((l) => !before.has(l.id)).map((l) => l.id));
        setReceiving(false);
      },
    },
  );

  const remaining = (l: DocLine) => Math.max(0, round3(l.qty - (l.receivedQty ?? 0)));
  const fillRemaining = () => setQtys(Object.fromEntries(po.lines.map((l) => [l.id, String(remaining(l)).replace(".", ",")])));
  const startReceive = () => { fillRemaining(); setCreatedLotIds([]); setReceiving(true); };
  const receiveLines = po.lines
    .map((l) => ({ lineId: l.id, receivedQty: num(qtys[l.id] ?? "0") }))
    .filter((r) => Number.isFinite(r.receivedQty) && r.receivedQty > 0);
  const invalid = po.lines.some((l) => { const v = num(qtys[l.id] ?? "0"); return !Number.isFinite(v) || v < 0; });

  const ordered = po.lines.reduce((s, l) => s + l.qty * l.unitPrice, 0);
  const receivedValue = po.lines.reduce((s, l) => s + Math.min(l.receivedQty, l.qty) * l.unitPrice, 0);
  const progress = ordered > 0 ? receivedValue / ordered : 0;
  const open = po.status === "sent" || po.status === "partially_received";
  const late = open && po.expectedDate < today;
  const busy = send.isPending || cancel.isPending || receive.isPending;
  const empty = po.lines.length === 0;
  const n = po.lines.length;

  const actions = receiving ? (
    <>
      <Button variant="ghost" onClick={() => setReceiving(false)} disabled={receive.isPending}>Annuler la saisie</Button>
      <Button variant="primary" icon={Check} loading={receive.isPending} disabled={!receiveLines.length || invalid} onClick={() => receive.mutate(receiveLines)}>
        Valider la réception
      </Button>
    </>
  ) : (
    <>
      {po.status === "draft" || open ? (
        <Button variant="danger" icon={Ban} loading={cancel.isPending} disabled={busy && !cancel.isPending}
          onClick={() => (armCancel ? cancel.mutate(undefined) : setArmCancel(true))}>
          {armCancel ? "Confirmer l'annulation" : "Annuler"}
        </Button>
      ) : null}
      {po.status === "draft" ? (
        <Button variant="primary" icon={Send} loading={send.isPending} disabled={busy || empty} title={empty ? "Ajoutez au moins une ligne" : undefined}
          onClick={() => send.mutate(undefined)}>Envoyer</Button>
      ) : null}
      {open ? <Button variant="primary" icon={PackageCheck} disabled={busy} onClick={startReceive}>Réceptionner</Button> : null}
    </>
  );

  return (
    <Page>
      <PageHeader
        breadcrumb={[{ label: "Achats", to: "/purchase-orders" }]}
        title={<span className="font-mono text-[13.5px]">{po.number}</span>}
        meta={<StatusDot kind="purchaseOrder" value={po.status} />}
        actions={actions}
      />
      <PageBody flush>
        <DocumentLayout
          kpis={
            <DocumentKpis
              doc={doc}
              products={products}
              partnerHint={<>{po.supplier.city || "—"} · délai {po.supplier.leadTimeDays} j</>}
              dateTone={late ? "destructive" : undefined}
              dateHint={late ? "En retard" : po.status === "received" ? "Reçue" : undefined}
              totalHint={doc.receiving ? <>{n} ligne{n > 1 ? "s" : ""} · reçu {fmtPercent(progress)}</> : undefined}
              createdHint={<DateLabel date={po.createdAt} format="relative" />}
            />
          }
          main={<>
            {po.status === "draft" || open ? <WarningList warnings={doc.warnings} /> : null}
            <LinesTable
              doc={doc}
              products={products}
              supplierPrices={supplierPrices}
              title={receiving ? "Réception · saisissez les quantités reçues" : undefined}
              actions={receiving ? (
                <span className="flex items-center gap-1">
                  <Button size="sm" variant="ghost" onClick={fillRemaining}>Tout le reste</Button>
                  <Button size="sm" variant="ghost" onClick={() => setQtys(Object.fromEntries(po.lines.map((l) => [l.id, "0"])))}>Vider</Button>
                </span>
              ) : undefined}
              frameClassName={receiving ? "rounded-[6px] ring-1 ring-primary/30" : undefined}
              footnote={receiving ? "Les quantités sont ajoutées à ce qui a déjà été reçu. Une ligne à 0 est ignorée." : undefined}
              extraColumn={receiving ? {
                header: "À réceptionner", width: 140, right: true, className: "py-0 pr-1",
                cell: (l) => (
                  <span className="inline-flex items-center justify-end gap-1">
                    <Input
                      size="sm"
                      inputMode="decimal"
                      aria-label={`Quantité reçue : ${l.productName}`}
                      value={qtys[l.id] ?? ""}
                      onChange={(e) => setQtys((q) => ({ ...q, [l.id]: e.target.value }))}
                      onKeyDown={(e) => { if (e.key === "Enter" && receiveLines.length && !invalid) receive.mutate(receiveLines); }}
                      className="num w-[68px] text-right"
                    />
                    <span className="w-6 text-left text-[11.5px] text-muted-foreground">{UNIT_LABEL[l.unit as keyof typeof UNIT_LABEL] ?? l.unit}</span>
                  </span>
                ),
              } : undefined}
            />
            <DocumentNote doc={doc} />
            {createdLotIds.length ? (
              <div className="flex items-center gap-2 rounded-[6px] border border-success/30 bg-success/10 px-3 py-2 text-[12.5px] text-success">
                <PackageCheck size={14} strokeWidth={1.75} />
                {createdLotIds.length} lot{createdLotIds.length > 1 ? "s" : ""} entré{createdLotIds.length > 1 ? "s" : ""} en stock, DLC calculée selon la durée de conservation.
              </div>
            ) : null}
            {po.status !== "draft" ? <LotsSection po={po} createdLotIds={createdLotIds} today={today} /> : null}
          </>}
          aside={<>
            <SupplierCard supplier={po.supplier} />
            <UsualBasket doc={doc} />
            <OtherOrders current={po.id} orders={supplier?.purchaseOrders} />
          </>}
        />
      </PageBody>
    </Page>
  );
}

function LotsSection({ po, createdLotIds, today }: { po: PurchaseOrderDetail; createdLotIds: string[]; today: string }) {
  const unitOf = (productId: string) => po.lines.find((l) => l.productId === productId)?.unit ?? "";
  const nameOf = (productId: string) => po.lines.find((l) => l.productId === productId)?.productName ?? productId;
  const cols: Column<Lot>[] = [
    {
      id: "product", header: "Produit",
      cell: (l) => (
        <span className="flex items-center gap-2">
          <span className="font-medium">{nameOf(l.productId)}</span>
          {createdLotIds.includes(l.id) ? <Badge tone="success">Nouveau</Badge> : null}
        </span>
      ),
    },
    { id: "lot", header: "Lot", width: 130, cell: (l) => <Mono>{l.id}</Mono> },
    { id: "receivedAt", header: "Reçu le", width: 120, cell: (l) => <DateLabel date={l.receivedAt} className="text-muted-foreground" /> },
    { id: "expires", header: "DLC", width: 150, cell: (l) => <ExpiryLabel date={l.expiresAt} today={today} /> },
    { id: "qty", header: "Quantité", width: 110, numeric: true, cell: (l) => <Qty value={l.qtyReceived} unit={unitOf(l.productId)} /> },
    { id: "remaining", header: "Restant", width: 110, numeric: true, cell: (l) => <Qty value={l.qtyRemaining} unit={unitOf(l.productId)} className="font-medium" /> },
  ];
  const lots = [...po.lots].sort((a, b) => Number(createdLotIds.includes(b.id)) - Number(createdLotIds.includes(a.id)) || b.receivedAt.localeCompare(a.receivedAt));
  return (
    <Section title="Lots reçus" count={po.lots.length}>
      <DataTable inset paginate={false} columns={cols} rows={lots} getRowId={(l) => l.id}
        empty={
          <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-border px-3 py-3 text-[12.5px] text-muted-foreground">
            <Boxes size={14} strokeWidth={1.75} />Aucun lot reçu pour l'instant.
          </div>
        } />
    </Section>
  );
}

/** Related documents: the other recent purchase orders at this supplier (open ones first). */
function OtherOrders({ current, orders }: { current: Id; orders?: PurchaseOrderSummary[] }) {
  const rank = (s: string) => (s === "draft" ? 0 : s === "sent" || s === "partially_received" ? 1 : 2);
  const list = (orders ?? []).filter((o) => o.id !== current)
    .sort((a, b) => rank(a.status) - rank(b.status) || b.createdAt.localeCompare(a.createdAt)).slice(0, 5);
  if (!list.length) return null;
  return (
    <Section title="Autres commandes" count={(orders?.length ?? 1) - 1}>
      <ul className="flex flex-col divide-y divide-border rounded-[6px] border border-border bg-card">
        {list.map((o) => (
          <li key={o.id}>
            {/* Two lines (number · total / status · date): the aside is too narrow for one. */}
            <Link to={`/purchase-orders/${o.id}`} className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-2 gap-y-0.5 whitespace-nowrap px-3 py-2 text-[12px] transition-colors hover:bg-muted/50">
              <Mono className="truncate text-[12px]">{o.number}</Mono>
              <Money value={o.totalHt} className="text-right" />
              <StatusDot kind="purchaseOrder" value={o.status} className="text-[12px]" />
              <span className="text-right text-muted-foreground"><DateLabel date={o.expectedDate} /></span>
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}
