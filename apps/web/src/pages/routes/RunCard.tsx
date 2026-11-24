/** One route run: header (route, driver, vehicle, departure), capacity bar, ordered stops with reorder
 *  (up/down buttons or drag) → PATCH /route-runs/:id/stops. Optimistic: the new order shows immediately. */
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowDown, ArrowUp, Clock, GripVertical, Truck, UserRound } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import type { Id, IsoDate, RouteRunDetail } from "@kit/shared";
import { api } from "@/lib/api";
import { fmtNumber, fmtPercent } from "@/lib/format";
import { qk, useApiMutation } from "@/lib/queries";
import { cn } from "@/lib/cn";
import { IconButton, Mono, Qty, StatusDot } from "@/ui";

type Stop = RouteRunDetail["stops"][number];

export function RunCard({ run, date }: { run: RouteRunDetail; date: IsoDate }) {
  const qc = useQueryClient();
  const serverOrder = [...run.stops].sort((a, b) => a.seq - b.seq);
  const serverKey = serverOrder.map((s) => s.orderId).join(",");
  const [order, setOrder] = useState<Id[]>(serverOrder.map((s) => s.orderId));
  const [dragId, setDragId] = useState<Id | null>(null);
  const [overId, setOverId] = useState<Id | null>(null);

  // Resync whenever the server order changes (refetch, live event).
  useEffect(() => { setOrder(serverKey ? serverKey.split(",") : []); }, [serverKey]);

  const reorder = useApiMutation((ids: Id[]) => api.routeRuns.reorderStops(run.id, ids), {
    success: "Ordre des arrêts mis à jour",
    onSuccess: (updated) => {
      qc.setQueryData<RouteRunDetail[]>(qk.routeRuns.list({ date }), (old) => old?.map((r) => (r.id === updated.id ? updated : r)));
      qc.invalidateQueries({ queryKey: qk.routeRuns.all });
    },
  });

  const byId = new Map(run.stops.map((s) => [s.orderId, s]));
  const stops = order.map((id) => byId.get(id)).filter((s): s is Stop => !!s);

  const commit = (next: Id[]) => {
    if (next.join(",") === order.join(",")) return;
    setOrder(next);
    reorder.mutate(next, { onError: () => setOrder(serverKey ? serverKey.split(",") : []) });
  };
  const move = (i: number, d: -1 | 1) => {
    const j = i + d;
    if (j < 0 || j >= order.length) return;
    const next = [...order];
    [next[i], next[j]] = [next[j], next[i]];
    commit(next);
  };
  const drop = (targetId: Id) => {
    if (!dragId || dragId === targetId) return;
    const next = order.filter((x) => x !== dragId);
    next.splice(next.indexOf(targetId), 0, dragId);
    commit(next);
  };

  const cap = run.route.capacityKg;
  const ratio = cap > 0 ? run.totalWeightKg / cap : 0;
  const capTone = ratio > 1 ? "bg-destructive" : ratio > 0.9 ? "bg-warning" : "bg-primary";
  const delivered = run.stops.filter((s) => s.status === "delivered").length;
  const editable = run.status !== "done";

  return (
    <section className="min-w-0 rounded-[6px] border border-border bg-card">
      <header className="border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <Truck size={15} strokeWidth={1.75} className="shrink-0 text-muted-foreground" />
          <h2 className="truncate text-[13.5px] font-semibold">{run.route.name}</h2>
          <span className="text-[12px] text-muted-foreground">{run.route.zone}</span>
          <span className="ml-auto shrink-0"><StatusDot kind="routeRun" value={run.status} /></span>
        </div>
        <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-secondary-foreground">
          <span className="inline-flex items-center gap-1"><UserRound size={12} strokeWidth={1.75} className="text-muted-foreground" />{run.route.driver || "—"}</span>
          <span className="truncate text-muted-foreground">{run.route.vehicle}</span>
          <span className="inline-flex items-center gap-1"><Clock size={12} strokeWidth={1.75} className="text-muted-foreground" />Départ <Mono className="text-foreground">{run.route.departureTime}</Mono></span>
        </div>
        <div className="mt-3">
          <div className="mb-1 flex items-center justify-between text-[12px]">
            <span className="text-muted-foreground">Charge</span>
            <span className={cn("num", ratio > 1 ? "text-destructive" : ratio > 0.9 ? "text-warning" : "text-secondary-foreground")}>
              {fmtNumber(Math.round(run.totalWeightKg))} / {fmtNumber(cap)} kg · {fmtPercent(ratio)}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-muted">
            <div className={cn("h-full rounded-full transition-[width]", capTone)} style={{ width: `${Math.min(100, ratio * 100)}%` }} />
          </div>
        </div>
      </header>

      {stops.length === 0 ? (
        <div className="px-4 py-6 text-center text-[12.5px] text-muted-foreground">Aucun arrêt sur cette tournée.</div>
      ) : (
        <ol className={cn("divide-y divide-border", reorder.isPending && "opacity-70")}>
          {stops.map((s, i) => (
            <li
              key={s.orderId}
              draggable={editable}
              onDragStart={(e) => { setDragId(s.orderId); e.dataTransfer.effectAllowed = "move"; }}
              onDragOver={(e) => { if (dragId) { e.preventDefault(); setOverId(s.orderId); } }}
              onDragLeave={() => setOverId((o) => (o === s.orderId ? null : o))}
              onDrop={(e) => { e.preventDefault(); drop(s.orderId); setDragId(null); setOverId(null); }}
              onDragEnd={() => { setDragId(null); setOverId(null); }}
              className={cn(
                "group flex items-center gap-2.5 py-1.5 pl-2 pr-2 transition-colors hover:bg-muted/50",
                dragId === s.orderId && "opacity-40",
                overId === s.orderId && dragId !== s.orderId && "bg-row-selected",
              )}
            >
              {editable ? <GripVertical size={13} strokeWidth={1.75} className="shrink-0 cursor-grab text-muted-foreground/60" aria-hidden /> : <span className="w-[13px]" />}
              <span className="num w-5 shrink-0 text-right text-[12px] font-medium text-muted-foreground">{i + 1}</span>
              <Mono className="w-11 shrink-0 text-[11.5px] text-muted-foreground">{s.eta ?? "—"}</Mono>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <Link to={`/clients/${s.clientId}`} className="truncate font-medium hover:underline">{s.clientName}</Link>
                  <span className="shrink-0 text-[12px] text-muted-foreground">{s.city}</span>
                </div>
                <div className="flex items-center gap-2 text-[11.5px]">
                  <Link to={`/orders/${s.orderId}`} className="hover:underline"><Mono className="text-[11.5px]">{s.orderNumber}</Mono></Link>
                  <Qty value={Math.round(s.weightKg * 10) / 10} unit="kg" className="text-secondary-foreground" />
                </div>
              </div>
              <span className="shrink-0"><StatusDot kind="stop" value={s.status} /></span>
              {editable ? (
                <span className="flex shrink-0 flex-col">
                  <IconButton icon={ArrowUp} size="sm" label="Monter" disabled={i === 0 || reorder.isPending} onClick={() => move(i, -1)} className="h-[18px] w-[22px]" />
                  <IconButton icon={ArrowDown} size="sm" label="Descendre" disabled={i === stops.length - 1 || reorder.isPending} onClick={() => move(i, 1)} className="h-[18px] w-[22px]" />
                </span>
              ) : null}
            </li>
          ))}
        </ol>
      )}

      <footer className="flex items-center justify-between border-t border-border px-4 py-2 text-[12px] text-muted-foreground">
        <span>{stops.length} arrêt{stops.length > 1 ? "s" : ""}</span>
        <span>{delivered}/{stops.length} livré{delivered > 1 ? "s" : ""}</span>
      </footer>
    </section>
  );
}
