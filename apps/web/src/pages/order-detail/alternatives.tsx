/** "Alternatives" side panel: /products/:id/alternatives, swap the line (substituteFor = original product). */
import { ArrowRightLeft, PackageSearch } from "lucide-react";
import type { Id, OrderDetail } from "@kit/shared";
import { api } from "@/lib/api";
import { categoryIds, categoryLabel, categoryOptions } from "@/lib/labels";
import { cn } from "@/lib/cn";
import { useProductAlternatives } from "@/lib/queries";
import { Button, DateLabel, EmptyState, Money, Mono, Qty, SECTION_LABEL, SidePanel, Skeleton } from "@/ui";
import { useDocWrite } from "@/features/document/model";

type Line = OrderDetail["lines"][number];

export function AlternativesPanel({ order, line, onClose }: { order: OrderDetail; line: Line; onClose: () => void }) {
  const { data, isLoading } = useProductAlternatives(line.productId);
  const swap = useDocWrite("sale", order.id, (productId: Id) =>
    api.orders.updateLine(order.id, line.id, { productId, substituteFor: line.substituteFor ?? line.productId }), "Ligne remplacée");
  const editable = order.status === "draft" || order.status === "confirmed";

  return (
    <SidePanel
      title="Alternatives"
      subtitle={<>Pour {line.productName} · <Qty value={line.qty} unit={line.unit} /></>}
      onClose={onClose}
    >
      <div className="mb-4 rounded-[4px] border border-border bg-muted/40 px-3 py-2 text-[12.5px] text-secondary-foreground">
        Même catégorie, en stock, prix proche. Le remplacement garde la quantité et reprend le prix client du nouveau produit.
        {order.client.preferences ? <div className="mt-1.5 text-muted-foreground">Préférences client : {order.client.preferences}</div> : null}
      </div>
      <div className={cn(SECTION_LABEL, "mb-2")}>Produits proposés</div>
      {isLoading ? (
        <div className="flex flex-col gap-2">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>
      ) : !data?.length ? (
        <EmptyState compact icon={PackageSearch} title="Aucune alternative en stock" description="Aucun produit comparable n'est disponible actuellement." />
      ) : (
        <ul className="flex flex-col divide-y divide-border rounded-[6px] border border-border">
          {data.map((p) => {
            const enough = p.available >= line.qty;
            const delta = line.unitPrice ? p.price / line.unitPrice - 1 : 0;
            return (
              <li key={p.id} className="flex items-center gap-3 px-3 py-2.5">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-medium">{p.name}</div>
                  <div className="mt-0.5 flex flex-wrap items-center gap-x-2 text-[11.5px] text-muted-foreground">
                    <Mono className="text-[11px] text-muted-foreground">{p.sku}</Mono>
                    <span>{categoryLabel(p.category)}</span>
                    {p.origin ? <span>· {p.origin}</span> : null}
                    {p.nextExpiry ? <span>· DLC <DateLabel date={p.nextExpiry} /></span> : null}
                  </div>
                </div>
                <div className="flex flex-col items-end gap-0.5 text-[12px]">
                  <span><Money value={p.price} /><span className="text-muted-foreground"> catalogue</span></span>
                  <span className={cn("num", Math.abs(delta) < 0.005 ? "text-muted-foreground" : delta > 0 ? "text-warning" : "text-success")}>
                    {Math.abs(delta) < 0.005 ? "même prix" : `${delta > 0 ? "+" : "−"}${Math.round(Math.abs(delta) * 100)} %`}
                  </span>
                </div>
                <div className="w-[84px] text-right text-[12px]">
                  <Qty value={p.available} unit={p.unit} tone={enough ? undefined : "warning"} />
                  <div className="text-[11px] text-muted-foreground">dispo</div>
                </div>
                <Button
                  size="sm"
                  icon={ArrowRightLeft}
                  disabled={!editable}
                  loading={swap.isPending && swap.variables === p.id}
                  onClick={() => swap.mutate(p.id, { onSuccess: onClose })}
                >
                  Remplacer
                </Button>
              </li>
            );
          })}
        </ul>
      )}
      {!editable ? <p className="mt-3 text-[11.5px] text-muted-foreground">La commande n'est plus modifiable : remplacement impossible.</p> : null}
    </SidePanel>
  );
}
