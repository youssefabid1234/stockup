/** Tournées — route runs by date (useRouteRuns), plan, reorder stops; route definitions in a second tab. */
import { Truck, CalendarDays, Wand2 } from "lucide-react";
import type { Route } from "@kit/shared";
import { api } from "@/lib/api";
import { fmtDateLong, parseDate } from "@/lib/format";
import { WEEKDAY_LABEL, WEEKDAYS } from "@/lib/labels";
import { qk, useApiMutation, useMeta, useRouteRuns, useRoutes } from "@/lib/queries";
import { useUrlState } from "@/lib/url-state";
import {
  Button, DataTable, DatePicker, EmptyState, Mono, Page, PageBody, PageHeader, Qty, Segmented, Skeleton, Tabs, type Column,
} from "@/ui";
import { RunCard } from "./RunCard";

const VIEWS = [
  { id: "runs", label: "Tournées du jour" },
  { id: "routes", label: "Définitions" },
] as const;
type View = (typeof VIEWS)[number]["id"];

const addDays = (iso: string, n: number) => {
  const d = parseDate(iso);
  d.setDate(d.getDate() + n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

export default function RoutesPage() {
  const { data: meta } = useMeta();
  const today = meta?.today ?? "";
  const tomorrow = today ? addDays(today, 1) : "";
  const [view, setView] = useUrlState("view", "runs");
  const [dateParam, setDate] = useUrlState("date");
  // ?date= takes an ISO day, or "today" / "tomorrow" (business clock, like the order lists); anything else = today.
  const date = dateParam === "tomorrow" ? tomorrow : /^\d{4}-\d{2}-\d{2}$/.test(dateParam) ? dateParam : today;

  const { data: runs, isError, refetch } = useRouteRuns(date ? { date } : undefined);
  const { data: routes } = useRoutes();
  const visibleRuns = date ? runs : undefined;

  const plan = useApiMutation(api.routeRuns.plan, {
    success: (r) => (r.length ? `${r.length} tournée${r.length > 1 ? "s" : ""} planifiée${r.length > 1 ? "s" : ""}` : "Aucune commande à planifier"),
    invalidate: [qk.routeRuns.all, qk.orders.all],
  });

  const quick = date === today ? "today" : date === tomorrow ? "tomorrow" : "other";
  const stopCount = visibleRuns?.reduce((s, r) => s + r.stops.length, 0) ?? 0;

  return (
    <Page>
      <PageHeader
        title="Tournées"
        tabs={<Tabs<View> value={view as View} onChange={setView} items={VIEWS.map((v) => ({ ...v, count: v.id === "routes" ? routes?.length : visibleRuns?.length }))} />}
        filters={view === "runs" ? (
          <>
            <Segmented
              value={quick}
              onChange={(v) => { if (v === "today") setDate(""); else if (v === "tomorrow") setDate(tomorrow); }}
              options={quick === "other"
                ? [{ id: "today", label: "Aujourd'hui" }, { id: "tomorrow", label: "Demain" }, { id: "other", label: "Autre" }]
                : [{ id: "today", label: "Aujourd'hui" }, { id: "tomorrow", label: "Demain" }]}
            />
            <DatePicker
              size="sm"
              aria-label="Date"
              value={date}
              onChange={(v) => setDate(v === today ? "" : v)}
              className="w-[150px]"
            />
          </>
        ) : null}
        actions={view === "runs" ? (
          <Button variant="primary" icon={Wand2} loading={plan.isPending} disabled={!date} onClick={() => plan.mutate(date)}>Planifier</Button>
        ) : null}
      />
      <PageBody flush={view === "routes"}>
        {view === "routes" ? (
          <RouteDefinitions routes={routes} />
        ) : isError && !runs ? (
          <EmptyState icon={Truck} title="Tournées indisponibles" description="L'API ne répond pas. Vérifiez que le serveur tourne sur le port 4000." action={<Button size="sm" onClick={() => refetch()}>Réessayer</Button>} />
        ) : !visibleRuns ? (
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-2 2xl:grid-cols-3">
            {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-[320px] w-full rounded-[6px]" />)}
          </div>
        ) : visibleRuns.length === 0 ? (
          <EmptyState
            icon={CalendarDays}
            title={`Aucune tournée le ${fmtDateLong(date)}`}
            description="« Planifier » regroupe les commandes confirmées et préparées de cette date par zone de livraison."
            action={<Button size="sm" icon={Wand2} loading={plan.isPending} onClick={() => plan.mutate(date)}>Planifier</Button>}
          />
        ) : (
          <>
            <div className="mb-4 text-[12.5px] text-muted-foreground">
              <span className="first-letter:uppercase">{fmtDateLong(date)}</span> · {visibleRuns.length} tournée{visibleRuns.length > 1 ? "s" : ""} · {stopCount} arrêt{stopCount > 1 ? "s" : ""}
            </div>
            <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-2 2xl:grid-cols-3">
              {[...visibleRuns].sort((a, b) => a.route.departureTime.localeCompare(b.route.departureTime) || a.route.name.localeCompare(b.route.name)).map((run) => (
                <RunCard key={run.id} run={run} date={date} />
              ))}
            </div>
          </>
        )}
      </PageBody>
    </Page>
  );
}

const ROUTE_COLS: Column<Route>[] = [
  { id: "name", header: "Tournée", sortValue: (r) => r.name, cell: (r) => <span className="font-medium">{r.name}</span> },
  { id: "zone", header: "Zone", width: 160, sortValue: (r) => r.zone, cell: (r) => r.zone },
  {
    id: "days", header: "Jours", width: 210,
    cell: (r) => (
      <span className="inline-flex gap-1.5">
        {WEEKDAYS.slice(0, 6).map((d) => (
          <span key={d} className={r.days.includes(d) ? "font-medium text-foreground" : "text-muted-foreground/50"}>{WEEKDAY_LABEL[d].replace(".", "")}</span>
        ))}
      </span>
    ),
  },
  { id: "dep", header: "Départ", width: 90, sortValue: (r) => r.departureTime, cell: (r) => <Mono>{r.departureTime}</Mono> },
  { id: "driver", header: "Chauffeur", width: 160, sortValue: (r) => r.driver, cell: (r) => r.driver || "—" },
  { id: "vehicle", header: "Véhicule", width: 200, muted: true, sortValue: (r) => r.vehicle, cell: (r) => r.vehicle || "—" },
  { id: "cap", header: "Capacité", width: 110, numeric: true, sortValue: (r) => r.capacityKg, cell: (r) => <Qty value={r.capacityKg} unit="kg" /> },
];

function RouteDefinitions({ routes }: { routes: Route[] | undefined }) {
  return (
    <DataTable
      columns={ROUTE_COLS}
      rows={routes}
      loading={!routes}
      getRowId={(r) => r.id}
      defaultSort={{ id: "name", dir: "asc" }}
      footer={routes ? `${routes.length} tournée${routes.length > 1 ? "s" : ""} définie${routes.length > 1 ? "s" : ""}` : undefined}
      empty={<EmptyState icon={Truck} title="Aucune tournée définie" description="Les tournées du data pack apparaîtront ici." />}
    />
  );
}
