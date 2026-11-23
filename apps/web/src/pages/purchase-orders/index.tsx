/** Achats — shared document list (features/document/list): status tabs with counts, search, expected date and supplier
 *  filters (?supplierId=); "Nouvelle commande d'achat" = supplier picker → empty draft → /purchase-orders/:id. */
import { useMemo } from "react";
import { ShoppingBasket } from "lucide-react";
import type { PurchaseOrderStatus } from "@kit/shared";
import { usePurchaseOrdersPage, useSuppliers } from "@/lib/queries";
import { Select } from "@/ui";
import { DocumentListPage, useDocListFilters, type DocRow } from "@/features/document/list";

const STATUS_TABS = [
  { id: "", label: "Toutes" },
  { id: "draft", label: "Brouillons" },
  { id: "sent", label: "Envoyées" },
  { id: "partially_received", label: "Partielles" },
  { id: "received", label: "Reçues" },
  { id: "cancelled", label: "Annulées" },
] as const;
const OPEN: PurchaseOrderStatus[] = ["sent", "partially_received"];

export default function PurchaseOrdersPage() {
  const f = useDocListFilters("supplierId");
  // Everything is server-side (one page per request): status tab, search, expected date, supplier, sort, page.
  const { data, isLoading, isError, refetch } = usePurchaseOrdersPage({ ...f.params, supplierId: f.partner || undefined });
  const { data: suppliers } = useSuppliers();
  const rows = useMemo<DocRow[] | undefined>(() => data?.items.map((p) => ({
    id: p.id, number: p.number, partnerName: p.supplierName, date: p.expectedDate, lineCount: p.lineCount, totalHt: p.totalHt, status: p.status,
    late: OPEN.includes(p.status) && p.expectedDate < f.today,
  })), [data, f.today]);
  const supplierOptions = useMemo(() => (suppliers ?? []).map((s) => ({ value: s.id, label: s.name, hint: s.city })), [suppliers]);

  return (
    <DocumentListPage
      kind="purchase"
      title="Achats"
      icon={ShoppingBasket}
      tabs={STATUS_TABS}
      filters={f}
      rows={rows}
      total={data?.total}
      counts={data?.counts}
      totalHt={data?.sums?.totalHt}
      loading={isLoading}
      error={isError}
      onRetry={() => refetch()}
      extraFilter={<Select size="sm" value={f.partner} onChange={f.setPartner} placeholder="Tous les fournisseurs" options={supplierOptions}
        aria-label="Fournisseur" className="w-[200px]" />}
      emptyText="Commandez auprès d'un fournisseur pour réapprovisionner le stock."
    />
  );
}
