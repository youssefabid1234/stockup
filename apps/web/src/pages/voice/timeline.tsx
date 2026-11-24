/** Two-track timeline: Appelant (left lane) and Agent (right lane); agent tool calls inline, violet. */
import { useLayoutEffect, useRef } from "react";
import { AudioLines, CircleAlert, Keyboard, Phone } from "lucide-react";
import { cn } from "@/lib/cn";
import { Dot, EmptyState, Kbd, SECTION_LABEL, Spinner } from "@/ui";
import { LiveTranscript } from "@/features/assistant/LiveTranscript";
import { ToolRow } from "@/features/assistant/tools";
import type { Activity, VoiceTurn } from "@/features/assistant/useVoiceSession";
import { TurnChips } from "./metrics";

const clock = (at?: number) => (at ? new Date(at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "");

const GRID = "grid grid-cols-[64px_minmax(0,1fr)_minmax(0,1fr)] gap-x-4";

export function Timeline({ turns, activity, level }: { turns: VoiceTurn[]; activity: Activity; level: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [turns]);

  return (
    <div
      ref={ref}
      className="min-h-0 flex-1 overflow-y-auto"
      onScroll={(e) => {
        const el = e.currentTarget;
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 60;
      }}
    >
      <div className={cn(GRID, "sticky top-0 z-10 border-b border-border bg-background px-5 py-2")}>
        <span />
        <span className={cn(SECTION_LABEL, "flex items-center gap-1.5")}><Phone size={12} strokeWidth={1.75} />Appelant</span>
        <span className={cn(SECTION_LABEL, "flex items-center gap-1.5 text-violet")}><AudioLines size={12} strokeWidth={1.75} />Agent</span>
      </div>
      {turns.length === 0 ? (
        <EmptyState
          icon={AudioLines}
          title="Jouez le client au téléphone"
          description="Maintenez Espace (ou le gros bouton) pour parler, relâchez pour que l'agent réponde. Les commandes qu'il crée apparaissent à droite, en direct."
          action={<span className="flex items-center gap-1.5 text-[12px] text-muted-foreground"><Kbd>Espace</Kbd> parler · <Kbd>Échap</Kbd> couper l'agent</span>}
        />
      ) : (
        <ol className="relative flex flex-col gap-3 px-5 py-4">
          {turns.map((t, i) => (
            <TurnRows key={t.id} t={t} last={i === turns.length - 1} activity={activity} level={level} />
          ))}
        </ol>
      )}
    </div>
  );
}

function TurnRows({ t, last, activity, level }: { t: VoiceTurn; last: boolean; activity: Activity; level: number }) {
  const c = t.caller;
  const a = t.agent;
  const agentStarted = a.text || a.tools.length || a.error;
  const thinking = !a.done && !agentStarted && c.status === "final";
  return (
    <li className="flex flex-col gap-2 animate-fade-in">
      {/* Caller */}
      <div className={GRID}>
        <time className="num pt-1.5 font-mono text-[10.5px] text-muted-foreground">{clock(c.at)}</time>
        <div className="flex min-w-0 justify-start">
          <div className="max-w-full rounded-[4px] border border-border bg-card px-3 py-2 text-[13px] shadow-sm">
            {c.status === "recording" ? (
              <span className="flex items-center gap-2">
                <Dot tone="violet" pulse className="shrink-0" />
                {c.text ? <LiveTranscript text={c.text} stable={c.stable} /> : <span className="text-violet">Parle…</span>}
                <LevelBars level={last ? level : 0} className="shrink-0" />
              </span>
            ) : c.status === "transcribing" ? (
              <span className="flex items-center gap-2 text-muted-foreground">
                <Spinner size={12} className="shrink-0" />
                {c.text ? <LiveTranscript text={c.text} stable={c.stable} /> : "Transcription…"}
              </span>
            ) : (
              <span className="flex items-start gap-1.5">
                {c.typed ? <Keyboard size={12} strokeWidth={1.75} className="mt-[3px] shrink-0 text-muted-foreground" aria-label="tapé" /> : null}
                <span>{c.text || <span className="text-muted-foreground">(rien entendu)</span>}</span>
              </span>
            )}
          </div>
        </div>
        <span />
      </div>

      {/* Agent */}
      {agentStarted || thinking || a.done ? (
        <div className={GRID}>
          <time className="num pt-1.5 font-mono text-[10.5px] text-muted-foreground">{clock(a.at)}</time>
          <span />
          <div className="flex min-w-0 flex-col items-start gap-1.5">
            {a.tools.map((tool) => <ToolRow key={tool.id} t={tool} className="w-full" />)}
            {thinking ? (
              <span className="flex h-8 items-center gap-2 text-[12px] text-violet"><Spinner size={12} />Réflexion…</span>
            ) : null}
            {a.text ? (
              <div
                className={cn(
                  "max-w-full whitespace-pre-wrap rounded-[4px] border border-violet/25 bg-violet/[.05] px-3 py-2 text-[13px]",
                  !a.done && "after:ml-0.5 after:inline-block after:h-3 after:w-[2px] after:animate-pulse after:bg-violet after:align-middle after:content-['']",
                  last && activity === "speaking" && "ring-2 ring-violet/20",
                )}
              >
                {a.text}
              </div>
            ) : null}
            {a.error ? (
              <span className="flex items-start gap-1.5 text-[12px] text-destructive"><CircleAlert size={13} strokeWidth={1.75} className="mt-[2px] shrink-0" />{a.error}</span>
            ) : null}
            {a.interrupted ? <span className="text-[11.5px] text-muted-foreground">Interrompu par l'appelant</span> : null}
            <TurnChips t={t} />
          </div>
        </div>
      ) : null}
    </li>
  );
}

/** 12-bar level meter fed by the AnalyserNode RMS (0..1). */
export function LevelBars({ level, className }: { level: number; className?: string }) {
  const n = 12;
  const lit = Math.round(level * n);
  return (
    <span className={cn("inline-flex h-3 items-end gap-[2px]", className)} aria-hidden>
      {Array.from({ length: n }).map((_, i) => (
        <span
          key={i}
          className={cn("w-[3px] rounded-[1px] transition-[height,background-color] duration-75", i < lit ? "bg-violet" : "bg-border")}
          style={{ height: `${30 + (i / (n - 1)) * 70}%` }}
        />
      ))}
    </span>
  );
}
