/** Activité — live feed of every write (SSE), server-paginated (useEventsPage: actor / entity filters by the API).
 *  Voice / AI events are tinted violet. */
import { useMemo, useRef } from "react";
import { Link } from "react-router-dom";
import { Activity, ArrowUpRight } from "lucide-react";
import type { ActivityEvent } from "@kit/shared";
import { cn } from "@/lib/cn";
import { businessNow } from "@/lib/clock";
import { fmtDateLong, fmtTime, parseDate } from "@/lib/format";
import { ACTOR_LABEL } from "@/lib/labels";
import { ENTITY_LABEL, entityPath } from "@/lib/links";
import { useEventsPage, useStreamStatus } from "@/lib/queries";
import { useUrlState } from "@/lib/url-state";
import { ActorIcon, Badge, Button, DateLabel, Dot, EmptyState, Page, PageBody, PageHeader, Pagination, SECTION_LABEL, Select, Skeleton, Tabs, isAiActor, usePagination, useServerList } from "@/ui";

type Filter = "" | "ai" | "user";
const ENTITY_OPTIONS = Object.entries(ENTITY_LABEL).map(([value, label]) => ({ value, label }));

export default function ActivityPage() {
  const status = useStreamStatus();
  const [who, setWho] = useUrlState("who");
  const [entity, setEntity] = useUrlState("entity");
  const mountedAt = useRef(businessNow().toISOString());

  // One page of the log per request; "user" = everything not written by an agent (user + system).
  const list = useServerList({ defaultSort: { id: "at", dir: "desc" } });
  const { data: page, isLoading, isError, refetch } = useEventsPage({
    actor: who === "ai" ? "ai" : who === "user" ? "user,system" : undefined, entity: entity || undefined, ...list.params,
  });
  const data = page?.items;
  const events = data ?? [];
  const total = page?.total ?? 0;

  // Pages of PAGE_SIZE events, then grouped by day (a day can span two pages; its header repeats).
  const pg = usePagination(data, { server: true, total: page?.total });
  const groups = useMemo(() => {
    const m = new Map<string, ActivityEvent[]>();
    for (const e of pg.rows) {
      const d = parseDate(e.at);
      const k = `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
      (m.get(k) ?? m.set(k, []).get(k)!).push(e);
    }
    return [...m.values()];
  }, [pg.rows]);

  // Tab counts {ai, user} over the entity filter (ignoring the actor tab), from the API.
  const counts = page?.counts;

  return (
    <Page>
      <PageHeader
        title="Activité"
        meta={
          <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <Dot tone={status === "live" ? "success" : status === "connecting" ? "warning" : "destructive"} pulse={status === "live"} />
            {status === "live" ? "En direct" : status === "connecting" ? "Connexion…" : "Hors ligne"}
          </span>
        }
        tabs={
          <Tabs<Filter>
            value={who as Filter}
            onChange={setWho}
            items={[
              { id: "", label: "Tout", count: counts ? (counts.ai ?? 0) + (counts.user ?? 0) : undefined },
              { id: "ai", label: "IA & voix", count: counts?.ai },
              { id: "user", label: "Équipe", count: counts?.user },
            ]}
          />
        }
        filters={<Select size="sm" value={entity} onChange={setEntity} placeholder="Tous les objets" options={ENTITY_OPTIONS} />}
      />
      <PageBody flush>
        {isLoading ? (
          <div className="flex flex-col">{Array.from({ length: 10 }).map((_, i) => (
            <div key={i} className="flex h-11 items-center gap-3 border-b border-border px-5"><Skeleton className="h-6 w-6 rounded-full" /><Skeleton className="h-3 w-[40%]" /><Skeleton className="ml-auto h-3 w-12" /></div>
          ))}</div>
        ) : isError && !data ? (
          <EmptyState icon={Activity} title="Journal indisponible" description="L'API ne répond pas." action={<Button size="sm" onClick={() => refetch()}>Réessayer</Button>} />
        ) : events.length === 0 ? (
          <EmptyState
            icon={Activity}
            title={counts && (counts.ai ?? 0) + (counts.user ?? 0) ? "Aucun événement pour ce filtre" : "Aucune activité pour l'instant"}
            description="Chaque écriture (commande, paiement, réception…) apparaît ici en temps réel — y compris celles de l'agent vocal."
          />
        ) : (
          <div ref={pg.anchorRef}>
            {groups.map((g) => (
              <section key={g[0].id}>
                <div className={cn(SECTION_LABEL, "sticky top-0 z-10 border-b border-border bg-background px-5 py-2")}>{fmtDateLong(g[0].at)}</div>
                <ol>{g.map((e) => <EventRow key={e.id} e={e} fresh={e.at > mountedAt.current} />)}</ol>
              </section>
            ))}
            <Pagination pagination={pg} sticky>{total} événement{total > 1 ? "s" : ""}</Pagination>
          </div>
        )}
      </PageBody>
    </Page>
  );
}

function EventRow({ e, fresh }: { e: ActivityEvent; fresh: boolean }) {
  const ai = isAiActor(e.actor);
  const to = entityPath(e.entity, e.entityId);
  return (
    <li
      className={cn(
        "group relative flex min-h-11 items-center gap-3 border-b border-border px-5 py-2 transition-colors",
        ai ? "bg-violet/[.045] hover:bg-violet/[.08]" : "hover:bg-muted/50",
        fresh && "animate-flash",
      )}
    >
      {ai ? <span className="absolute inset-y-0 left-0 w-[2px] bg-violet" aria-hidden /> : null}
      <ActorIcon actor={e.actor} />
      <div className="min-w-0 flex-1">
        <div className="truncate text-[13px]">{e.summary}</div>
        <div className="mt-0.5 flex items-center gap-2 text-[11.5px] text-muted-foreground">
          <span className={cn(ai && "text-violet")}>{e.actorName || ACTOR_LABEL[e.actor]}</span>
          <span>·</span>
          <span className="font-mono text-[11px]">{e.type}</span>
        </div>
      </div>
      {ai ? <Badge tone="violet">{ACTOR_LABEL[e.actor]}</Badge> : null}
      {to ? (
        <Link to={to} className="inline-flex items-center gap-1 text-[12px] text-muted-foreground hover:text-foreground">
          {ENTITY_LABEL[e.entity]}<ArrowUpRight size={12} />
        </Link>
      ) : null}
      <span className="num w-[70px] text-right text-[12px] text-muted-foreground" title={fmtTime(e.at)}>
        <DateLabel date={e.at} format="relative" />
      </span>
    </li>
  );
}
