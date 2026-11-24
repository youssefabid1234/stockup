/** Commandes — shared document list (features/document/list): status tabs with counts, search (n° / client), delivery
 *  date, channel filter (?clientId= still filters by client); "Nouvelle commande" = client picker → empty draft → /orders/:id.
 *  Server-side pagination: one page of 100 per request (GET /api/orders?envelope=1). */
import { useMemo } from "react";
import { ShoppingCart } from "lucide-react";
import { useOrdersPage } from "@/lib/queries";
import { useUrlState } from "@/lib/url-state";
import { Select } from "@/ui";
import { DocumentListPage, useDocListFilters, type DocRow } from "@/features/document/list";
import { SOURCE_OPTIONS, SourceLabel } from "./source";

const STATUS_TABS = [
  { id: "", label: "Toutes" },
  { id: "draft", label: "Pré-commandes" },
  { id: "confirmed", label: "Confirmées" },
  { id: "prepared", label: "Préparées" },
  { id: "delivered", label: "Livrées" },
  { id: "invoiced", label: "Facturées" },
  { id: "cancelled", label: "Annulées" },
] as const;

export default function OrdersPage() {
  const f = useDocListFilters("clientId");
  const [source, setSource] = useUrlState("source");
  // Everything is server-side (one page per request): status tab, search, date, client, channel, sort, page.
  const { data, isLoading, isError, refetch } = useOrdersPage({ ...f.params, clientId: f.partner || undefined, source: source || undefined });
  const rows = useMemo<DocRow[] | undefined>(() => data?.items.map((o) => ({
    id: o.id, number: o.number, partnerName: o.clientName, date: o.deliveryDate, lineCount: o.lineCount, totalHt: o.totalHt, status: o.status,
    partnerExtra: o.source === "voice_agent" ? <SourceLabel source={o.source} /> : undefined,
  })), [data]);

  return (
    <DocumentListPage
      kind="sale"
      title="Commandes"
      icon={ShoppingCart}
      tabs={STATUS_TABS}
      filters={f}
      rows={rows}
      total={data?.total}
      counts={data?.counts}
      totalHt={data?.sums?.totalHt}
      loading={isLoading}
      error={isError}
      onRetry={() => refetch()}
      extraFilter={<Select size="sm" value={source} onChange={setSource} placeholder="Tous canaux" options={SOURCE_OPTIONS} aria-label="Canal" className="w-[150px]" />}
      extraActive={!!source}
      onResetExtra={() => setSource("")}
      emptyText="Les commandes saisies, reçues par téléphone ou prises par l'agent vocal apparaîtront ici."
    />
  );
}
