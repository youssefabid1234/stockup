/** Order detail related documents (side column): invoice and delivery route. Client card and usual basket are shared (features/document). */
import { Link } from "react-router-dom";
import { ArrowUpRight, FileText, Truck } from "lucide-react";
import type { OrderDetail } from "@kit/shared";
import { fmtQty } from "@/lib/format";
import { useRouteRuns } from "@/lib/queries";
import { DateLabel, KeyValue, Money, Mono, Section, Skeleton, StatusDot } from "@/ui";

export function InvoiceSection({ order }: { order: OrderDetail }) {
  const inv = order.invoice;
  if (!inv) return null;
  return (
    <Section title="Facture">
      <Link to={`/invoices/${inv.id}`} className="flex items-center gap-3 rounded-[6px] border border-border bg-card px-3 py-2.5 transition-colors hover:bg-muted/50">
        <FileText size={15} strokeWidth={1.75} className="text-muted-foreground" />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2"><Mono>{inv.number}</Mono><StatusDot kind="invoice" value={inv.status} /></div>
          <div className="mt-0.5 text-[11.5px] text-muted-foreground">Émise <DateLabel date={inv.issuedAt} /> · échéance <DateLabel date={inv.dueDate} /></div>
        </div>
        <div className="text-right">
          <Money value={inv.totalTtc} className="font-medium" />
          {inv.balance > 0 ? <div className="text-[11.5px] text-muted-foreground">reste <Money value={inv.balance} tone={inv.daysOverdue > 0 ? "destructive" : undefined} /></div> : <div className="text-[11.5px] text-success">soldée</div>}
        </div>
      </Link>
    </Section>
  );
}

export function RouteSection({ order }: { order: OrderDetail }) {
  const { data, isLoading } = useRouteRuns({ date: order.deliveryDate });
  const run = data?.find((r) => r.id === order.routeRunId) ?? data?.find((r) => r.stops.some((s) => s.orderId === order.id));
  const stop = run?.stops.find((s) => s.orderId === order.id);

  return (
    <Section title="Tournée" actions={<Link to="/routes" className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground">Tournées<ArrowUpRight size={12} /></Link>}>
      {isLoading ? (
        <Skeleton className="h-14 w-full" />
      ) : !run ? (
        <div className="flex items-center gap-2 rounded-[6px] border border-dashed border-border px-3 py-3 text-[12.5px] text-muted-foreground">
          <Truck size={14} strokeWidth={1.75} />
          {order.status === "draft" ? "Affectée à une tournée à la confirmation." : order.status === "cancelled" ? "Commande annulée." : "Pas encore planifiée sur une tournée."}
        </div>
      ) : (
        <div className="rounded-[6px] border border-border bg-card px-3 py-2.5">
          <div className="flex items-center gap-2">
            <Truck size={14} strokeWidth={1.75} className="text-muted-foreground" />
            <span className="truncate font-medium">{run.route.name}</span>
            <StatusDot kind="routeRun" value={run.status} className="ml-auto" />
          </div>
          <KeyValue
            className="mt-2"
            labelWidth={100}
            items={[
              { label: "Départ", value: <><DateLabel date={run.date} /> · {run.route.departureTime}</> },
              { label: "Chauffeur", value: run.route.driver },
              { label: "Véhicule", value: run.route.vehicle },
              ...(stop ? [{ label: "Arrêt", value: <span className="inline-flex items-center gap-2"><span className="num">n° {stop.seq} / {run.stops.length}</span>{stop.eta ? <span className="num text-muted-foreground">ETA {stop.eta}</span> : null}<StatusDot kind="stop" value={stop.status} /></span> }] : []),
              { label: "Charge", value: <span className="num">{fmtQty(run.totalWeightKg, "kg")} / {fmtQty(run.route.capacityKg, "kg")}</span> },
            ]}
          />
        </div>
      )}
    </Section>
  );
}

