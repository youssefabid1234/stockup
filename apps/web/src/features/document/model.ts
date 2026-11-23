/**
 * One model for both commercial documents: a sale order (client) and a purchase order (supplier).
 * Pages map their API detail into a `DocModel`; every shared block (lines, totals, usual basket, warnings, header strip)
 * reads only this model plus `kind`, and writes through `useDocOps`.
 */
import { useQueryClient } from "@tanstack/react-query";
import type { Id, OrderDetail, ProductSummary, PurchaseOrderDetail, Warning } from "@kit/shared";
import { api } from "@/lib/api";
import { qk, useApiMutation } from "@/lib/queries";

export type DocKind = "sale" | "purchase";

export interface DocLine {
  id: Id;
  productId: Id;
  productName: string;
  unit: string;
  qty: number;
  unitPrice: number;
  /** sale */
  note?: string;
  available?: number;
  preparedQty?: number;
  substituteFor?: Id;
  /** purchase */
  receivedQty?: number;
}

export interface DocModel {
  kind: DocKind;
  id: Id;
  number: string;
  status: string;
  partnerId: Id;
  partnerName: string;
  /** Delivery date (sale) or expected date (purchase). */
  date: string;
  note?: string;
  createdAt: string;
  lines: DocLine[];
  warnings: Warning[];
  /** Lines can be added / edited / removed. */
  editable: boolean;
  /** Date and note can be edited. */
  headerEditable: boolean;
  /** Sale only: prepared status, weighed quantities are typed in. */
  preparing?: boolean;
  /** Sale only: delivered quantity = prepared quantity. */
  picked?: boolean;
  /** Purchase only: sent or later, received quantities are shown. */
  receiving?: boolean;
  /** Final totals when the document is frozen (invoice). */
  frozenTotals?: { ht: number; vat: number; ttc: number };
}

/** Labels that differ between the two sides; everything else is shared. */
export const KIND = {
  sale: {
    list: "/orders", listLabel: "Commandes", partner: "Client", partnerPath: "/clients", detailPath: "/orders",
    date: "Livraison", dateHint: "Modifiable jusqu'à la préparation", noun: "commande", newLabel: "Nouvelle commande",
    usualEmpty: "Pas encore d'historique pour ce client.", notePlaceholder: "Consigne de livraison, remarque du client…",
  },
  purchase: {
    list: "/purchase-orders", listLabel: "Achats", partner: "Fournisseur", partnerPath: "/suppliers", detailPath: "/purchase-orders",
    date: "Livraison prévue", dateHint: "Modifiable jusqu'à la réception", noun: "commande d'achat", newLabel: "Nouvelle commande d'achat",
    usualEmpty: "Pas encore d'achat récent chez ce fournisseur.", notePlaceholder: "Consigne de livraison, quai, remarque pour le fournisseur…",
  },
} as const;

const PICKED = new Set(["prepared", "delivered", "invoiced"]);

export function orderToDoc(o: OrderDetail): DocModel {
  const editable = o.status === "draft" || o.status === "confirmed";
  return {
    kind: "sale", id: o.id, number: o.number, status: o.status, partnerId: o.clientId, partnerName: o.client.name,
    date: o.deliveryDate, note: o.note, createdAt: o.createdAt, warnings: o.warnings,
    lines: o.lines.map((l) => ({ ...l })),
    editable, headerEditable: editable, preparing: o.status === "prepared", picked: PICKED.has(o.status),
    frozenTotals: o.invoice ? { ht: o.invoice.totalHt, vat: o.invoice.totalVat, ttc: o.invoice.totalTtc } : undefined,
  };
}

export function purchaseToDoc(po: PurchaseOrderDetail): DocModel {
  const open = po.status === "draft" || po.status === "sent";
  return {
    kind: "purchase", id: po.id, number: po.number, status: po.status, partnerId: po.supplierId, partnerName: po.supplier.name,
    date: po.expectedDate, note: po.note, createdAt: po.createdAt, warnings: po.warnings ?? [],
    lines: po.lines.map((l) => ({ ...l })),
    editable: po.status === "draft", headerEditable: open, receiving: po.status !== "draft" && po.status !== "cancelled",
  };
}

/** Quantity that counts for the totals (prepared qty once picked). */
export const lineQty = (d: DocModel, l: DocLine) => (d.picked ? l.preparedQty ?? l.qty : l.qty);

export function computeTotals(d: DocModel, products: Map<Id, ProductSummary>) {
  if (d.frozenTotals) return d.frozenTotals;
  let ht = 0, vat = 0;
  for (const l of d.lines) {
    const t = lineQty(d, l) * l.unitPrice;
    ht += t;
    vat += t * (products.get(l.productId)?.vatRate ?? 0.055);
  }
  ht = Math.round(ht * 100) / 100;
  vat = Math.round(vat * 100) / 100;
  return { ht, vat, ttc: Math.round((ht + vat) * 100) / 100 };
}

/** Default quantity when adding from a usual basket: rounded average, at least one unit (0.5 kg). */
export const roundQty = (q: number, unit: string) => (unit === "kg" || unit === "liter" ? Math.round(q * 2) / 2 : Math.max(1, Math.round(q)));
export const usualQty = (avg: number, unit: string) => Math.max(roundQty(avg, unit), unit === "kg" ? 0.5 : 1);

const SALE_INVALIDATE = [qk.orders.all, qk.dashboard, qk.stock.all, qk.products.all];
const PURCHASE_INVALIDATE = [qk.purchaseOrders.all, qk.suppliers.all, qk.dashboard];

/**
 * Write on a document that returns the fresh detail: puts it straight in the cache (no flicker) and refreshes lists.
 * Returns `{ id }` on purpose: warnings are recomputed on every read, so letting useApiMutation toast them would re-toast
 * the same warnings on each line edit. They are shown inline instead (and toasted once on confirm / send).
 */
export function useDocWrite<V>(kind: DocKind, id: Id, fn: (v: V) => Promise<OrderDetail | PurchaseOrderDetail>, success?: string) {
  const qc = useQueryClient();
  return useApiMutation(
    async (v: V) => {
      const d = await fn(v);
      qc.setQueryData(kind === "sale" ? qk.orders.detail(id) : qk.purchaseOrders.detail(id), d);
      return { id: d.id };
    },
    { success, invalidate: kind === "sale" ? SALE_INVALIDATE : PURCHASE_INVALIDATE },
  );
}

export interface LinePatch { qty?: number; unitPrice?: number; note?: string; preparedQty?: number; productId?: Id; substituteFor?: Id }

/** Line and header writes, routed to the orders or purchase-orders API. */
export function useDocOps(d: Pick<DocModel, "kind" | "id">) {
  const { kind, id } = d;
  const sale = kind === "sale";
  const add = useDocWrite(kind, id, (v: { productId: Id; qty: number }) =>
    sale ? api.orders.addLine(id, v) : api.purchaseOrders.addLine(id, v), "Produit ajouté");
  const update = useDocWrite(kind, id, (v: { lineId: Id; patch: LinePatch }) => {
    if (sale) return api.orders.updateLine(id, v.lineId, v.patch);
    const { qty, unitPrice, productId } = v.patch;
    return api.purchaseOrders.updateLine(id, v.lineId, { qty, unitPrice, productId });
  });
  const remove = useDocWrite(kind, id, (lineId: Id) => (sale ? api.orders.removeLine(id, lineId) : api.purchaseOrders.removeLine(id, lineId)), "Ligne retirée");
  const setDate = useDocWrite(kind, id, (date: string) =>
    sale ? api.orders.update(id, { deliveryDate: date }) : api.purchaseOrders.update(id, { expectedDate: date }),
  sale ? "Date de livraison modifiée" : "Date de livraison prévue modifiée");
  const setNote = useDocWrite(kind, id, (note: string) => (sale ? api.orders.update(id, { note }) : api.purchaseOrders.update(id, { note })), "Note enregistrée");
  return { add, update, remove, setDate, setNote };
}
