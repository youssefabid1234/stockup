/** Right column: live ERP events written by the voice agent (x-actor: voice_agent), with links. */
import { useCallback, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Activity, ArrowUpRight } from "lucide-react";
import type { ActivityEvent } from "@kit/shared";
import { cn } from "@/lib/cn";
import { businessNow } from "@/lib/clock";
import { ENTITY_LABEL, entityPath } from "@/lib/links";
import { useEvents, useOnActivity, useStreamStatus } from "@/lib/queries";
import { DateLabel, Dot, EmptyState, SECTION_LABEL, Skeleton } from "@/ui";

export function LiveActivity() {
  const { data, isLoading } = useEvents(200);
  const status = useStreamStatus();
  const mountedAt = useRef(businessNow().toISOString());
  const [fresh, setFresh] = useState<Set<string>>(() => new Set());

  // Live events land in the events cache on their own; this only marks the new voice ones to flash them.
  const onEvent = useCallback((e: ActivityEvent) => {
    if (e.actor !== "voice_agent") return;
    setFresh((s) => new Set(s).add(e.id));
  }, []);
  useOnActivity(onEvent);

  const events = useMemo(() => (data ?? []).filter((e) => e.actor === "voice_agent").slice(0, 60), [data]);
  const sessionCount = events.filter((e) => e.at > mountedAt.current || fresh.has(e.id)).length;

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-10 shrink-0 items-center gap-2 border-b border-border px-4">
        <span className={SECTION_LABEL}>ERP en direct</span>
        <span className="num text-[11.5px] text-muted-foreground">{sessionCount ? `+${sessionCount} cette session` : ""}</span>
        <span className="ml-auto flex items-center gap-1.5 text-[11.5px] text-muted-foreground">
          <Dot tone={status === "live" ? "success" : status === "connecting" ? "warning" : "destructive"} pulse={status === "live"} />
          {status === "live" ? "En direct" : status === "connecting" ? "Connexion…" : "Hors ligne"}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading ? (
          Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="flex flex-col gap-1.5 border-b border-border px-4 py-2.5"><Skeleton className="h-3 w-[80%]" /><Skeleton className="h-2.5 w-24" /></div>
          ))
        ) : events.length === 0 ? (
          <EmptyState
            compact
            icon={Activity}
            title="Aucune écriture de l'agent vocal"
            description="Demandez une pré-commande : elle apparaît ici dès que l'agent l'écrit dans l'ERP."
          />
        ) : (
          <ol>{events.map((e) => <Row key={e.id} e={e} fresh={fresh.has(e.id)} />)}</ol>
        )}
      </div>
    </div>
  );
}

function Row({ e, fresh }: { e: ActivityEvent; fresh: boolean }) {
  const to = entityPath(e.entity, e.entityId);
  const body = (
    <>
      <span className="absolute inset-y-0 left-0 w-[2px] bg-violet" aria-hidden />
      <div className="min-w-0 flex-1">
        <div className="line-clamp-2 text-[12.5px] leading-[17px]">{e.summary}</div>
        <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-muted-foreground">
          <span className="font-mono text-[10.5px] text-violet">{e.type}</span>
          <span>·</span>
          <DateLabel date={e.at} format="relative" />
        </div>
      </div>
      {to ? (
        <span className="mt-0.5 inline-flex shrink-0 items-center gap-0.5 text-[11.5px] text-muted-foreground group-hover:text-foreground">
          {ENTITY_LABEL[e.entity]}<ArrowUpRight size={11} />
        </span>
      ) : null}
    </>
  );
  const cls = cn("group relative flex items-start gap-2 border-b border-border bg-violet/[.03] px-4 py-2.5 transition-colors hover:bg-violet/[.07]", fresh && "animate-flash");
  return <li>{to ? <Link to={to} className={cls}>{body}</Link> : <div className={cls}>{body}</div>}</li>;
}
