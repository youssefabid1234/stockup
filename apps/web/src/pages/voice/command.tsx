/**
 * Voix · Commande (un tour) — the user drives the ERP by voice, one utterance at a time (POST /ai/command, stateless).
 * Hold Space here (or ⌥ Space on any page, or the big button), say the command, release.
 * History of commands (newest first): transcript, ERP tool rows, one-line answer + links, latency chips. Live ERP column on the right.
 */
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { AudioLines, Gauge, Mic, MicOff, Send, Trash2, Volume2, VolumeX } from "lucide-react";
import { cn } from "@/lib/cn";
import { Button, Dot, EmptyState, IconButton, Input, Kbd, Page, PageHeader, SECTION_LABEL, Spinner } from "@/ui";
import { useAiHealth } from "@/features/assistant/ai-client";
import {
  clearCommandHistory, COMMAND_METRICS, LevelMeter, metricValue, MsChip, RunBody, RunChips, sendCommandText, setSpeak,
  startCommand, stopCommand, stopSpeaking, useVoiceCommand, VOICE_COMMAND_HINT, type CommandRun, type CommandState,
} from "@/features/voice-command";
import { LiveActivity } from "./live-activity";

const EXAMPLES = [
  "Crée une pré-commande pour Lemoine, 4 kilos de bar pour jeudi",
  "Montre-moi le stock de turbot",
  "Marque la facture FAC-2026-011590 comme payée par virement",
];

const isTypingTarget = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
};

const PHASE_LABEL: Record<CommandState["phase"], string> = {
  idle: "Prêt", recording: "J'écoute…", working: "J'exécute…", done: "Prêt", error: "Prêt",
};

export function CommandMode({ modeSwitch }: { modeSwitch: ReactNode }) {
  const s = useVoiceCommand();
  const health = useAiHealth();
  const [text, setText] = useState("");
  const spaceDown = useRef(false);

  // Space = hold to talk (outside text fields). ⌥ Space works everywhere via the global provider.
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !isTypingTarget(e.target) && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        if (e.repeat || spaceDown.current) return;
        spaceDown.current = true;
        void startCommand();
      } else if (e.key === "Escape") {
        stopSpeaking();
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code !== "Space" || !spaceDown.current) return;
      e.preventDefault();
      spaceDown.current = false;
      stopCommand();
    };
    const blur = () => { if (spaceDown.current) { spaceDown.current = false; stopCommand(); } };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", blur);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", blur);
    };
  }, []);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    sendCommandText(text);
    setText("");
  };

  const online = health.isSuccess;
  const runs = [...s.runs].reverse();
  const p = health.data;

  return (
    <Page>
      <PageHeader
        title="Voix"
        meta={
          <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
            <Dot tone={online ? "success" : health.isLoading ? "warning" : "destructive"} pulse={health.isLoading} />
            {online ? "Service IA prêt" : health.isLoading ? "Connexion…" : "Service IA injoignable"}
          </span>
        }
        tabs={modeSwitch}
        actions={
          <>
            {/* Active providers (not filters): informative chips, only where there is room. */}
            {p ? (
              <div className="hidden items-center gap-1 xl:flex">
                <ProviderChip k="llm" v={`${p.llm.provider}${p.llm.model ? `:${p.llm.model}` : ""}`} />
                <ProviderChip k="stt" v={p.stt.provider} />
                <ProviderChip k="tts" v={p.tts.provider} />
              </div>
            ) : null}
            <Button size="sm" variant="ghost" icon={s.speak ? Volume2 : VolumeX} onClick={() => setSpeak(!s.speak)} aria-pressed={s.speak}>
              {s.speak ? "Réponse vocale" : "Réponse muette"}
            </Button>
            <Button size="sm" icon={Trash2} onClick={clearCommandHistory} disabled={!s.runs.length}>Effacer</Button>
          </>
        }
      />
      <div className="flex min-h-0 flex-1">
        <section className="flex min-w-0 flex-1 flex-col">
          <AverageBar runs={s.runs} />
          <div className="min-h-0 flex-1 overflow-y-auto">
            {runs.length === 0 ? (
              <EmptyState
                icon={AudioLines}
                title="Pilotez l'ERP à la voix, une commande à la fois"
                description="Maintenez Espace (ou ⌥ Espace sur n'importe quelle page), dites la commande, relâchez : l'agent l'exécute et répond en une ligne."
                action={
                  <div className="flex flex-col items-center gap-1.5">
                    {EXAMPLES.map((ex) => (
                      <button
                        key={ex}
                        type="button"
                        onClick={() => sendCommandText(ex)}
                        className="rounded-[3px] border border-violet/20 bg-violet/[.05] px-2 py-1 text-[12px] text-secondary-foreground transition-colors hover:border-violet/40 hover:text-foreground"
                      >
                        « {ex} »
                      </button>
                    ))}
                  </div>
                }
              />
            ) : (
              <ol>{runs.map((r) => <HistoryRow key={r.id} r={r} live={r.id === s.current && s.phase !== "done" && s.phase !== "error"} />)}</ol>
            )}
          </div>

          {s.mic === "denied" || s.mic === "unsupported" ? (
            <div className="flex shrink-0 items-center gap-2 border-t border-border bg-warning/[.08] px-5 py-2 text-[12px]">
              <MicOff size={14} strokeWidth={1.75} className="shrink-0 text-warning" />
              <span>
                {s.mic === "denied"
                  ? "Micro refusé : autorisez-le dans les réglages du site (icône à gauche de l'adresse), puis réessayez. En attendant, tapez la commande."
                  : "Micro indisponible dans ce navigateur (il faut localhost ou https). Tapez la commande."}
              </span>
            </div>
          ) : null}

          <div className="flex shrink-0 items-center gap-4 border-t border-border px-5 py-3">
            <HoldButton recording={s.phase === "recording"} disabled={!online} />
            <div className="flex w-[200px] shrink-0 flex-col gap-1">
              <span className={cn("flex items-center gap-1.5 text-[13px] font-medium", (s.phase === "recording" || s.phase === "working") && "text-violet")}>
                {s.phase === "working" ? <Spinner size={12} /> : s.phase === "recording" ? <Dot tone="violet" pulse /> : null}
                {online ? PHASE_LABEL[s.phase] : "Hors ligne"}
              </span>
              {s.phase === "recording" ? (
                <LevelMeter level={s.level} n={12} />
              ) : (
                <span className="flex items-center gap-1 text-[11.5px] text-muted-foreground">
                  <Kbd>Espace</Kbd> ici · <Kbd>{VOICE_COMMAND_HINT}</Kbd> partout
                </span>
              )}
            </div>
            <form onSubmit={submit} className="flex min-w-0 flex-1 items-center gap-2">
              <Input
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Escape") (e.target as HTMLInputElement).blur(); }}
                placeholder="Ou tapez la commande : « montre-moi le stock de turbot »…"
                disabled={!online}
                className="min-w-0 flex-1"
              />
              <IconButton type="submit" icon={Send} label="Exécuter" variant="default" disabled={!online || !text.trim()} />
            </form>
          </div>
        </section>
        <aside className="w-[280px] shrink-0 border-l border-border bg-card xl:w-[320px] 2xl:w-[380px]">
          <LiveActivity />
        </aside>
      </div>
    </Page>
  );
}

const clock = (at: number) => new Date(at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

function HistoryRow({ r, live }: { r: CommandRun; live: boolean }) {
  return (
    <li className={cn("grid grid-cols-[64px_minmax(0,1fr)] gap-x-4 border-b border-border px-5 py-3", live && "bg-violet/[.03]")}>
      <time className="num pt-0.5 font-mono text-[10.5px] text-muted-foreground">{clock(r.at)}</time>
      <div className="flex min-w-0 max-w-[760px] flex-col gap-1.5">
        <RunBody r={r} compact />
        <RunChips r={r} />
      </div>
    </li>
  );
}

/** Running averages over the commands of this session. */
function AverageBar({ runs }: { runs: CommandRun[] }) {
  const measured = runs.filter((r) => r.timings);
  const avg = (k: (typeof COMMAND_METRICS)[number]["key"]) => {
    const xs = runs.map((r) => metricValue(r, k)).filter((x): x is number => x != null);
    return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : undefined;
  };
  return (
    <div className="flex min-h-10 shrink-0 flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-5 py-1.5">
      <span className={cn(SECTION_LABEL, "flex items-center gap-1.5")}>
        <Gauge size={13} strokeWidth={1.75} />
        Latence moyenne
      </span>
      <span className="num text-[11.5px] text-muted-foreground">
        {measured.length ? `${measured.length} commande${measured.length > 1 ? "s" : ""}` : "aucune commande mesurée"}
      </span>
      <div className="flex min-w-0 flex-wrap items-center gap-1">
        {COMMAND_METRICS.map((m) => <MsChip key={m.key} k={m.key} label={m.label} ms={avg(m.key)} title={m.title} />)}
      </div>
    </div>
  );
}

function ProviderChip({ k, v }: { k: string; v: string }) {
  return (
    <span className="inline-flex h-[20px] max-w-[220px] items-center gap-1 truncate rounded-[3px] border border-border px-1.5 font-mono text-[10.5px]" title={`${k} : ${v}`}>
      <span className="text-muted-foreground">{k}</span>
      <span className="truncate text-secondary-foreground">{v}</span>
    </span>
  );
}

function HoldButton({ recording, disabled }: { recording: boolean; disabled: boolean }) {
  const held = useRef(false);
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label="Maintenir pour dire une commande"
      aria-pressed={recording}
      onPointerDown={(e) => {
        if (e.button !== 0) return;
        e.currentTarget.setPointerCapture(e.pointerId);
        held.current = true;
        void startCommand();
      }}
      onPointerUp={() => { if (held.current) { held.current = false; stopCommand(); } }}
      onPointerCancel={() => { if (held.current) { held.current = false; stopCommand(); } }}
      onKeyDown={(e) => { if (e.key === "Enter") e.preventDefault(); }}
      onContextMenu={(e) => e.preventDefault()}
      className={cn(
        "relative flex h-14 w-14 shrink-0 select-none items-center justify-center rounded-full border transition-[transform,background-color,border-color] duration-100",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet/70 disabled:opacity-40",
        recording
          ? "scale-95 border-violet bg-violet text-primary-foreground"
          : "border-violet/40 bg-violet/10 text-violet hover:border-violet hover:bg-violet/15",
      )}
      style={{ touchAction: "none" }}
    >
      {recording ? <span className="absolute inset-0 animate-ping rounded-full bg-violet/30" aria-hidden /> : null}
      <Mic size={22} strokeWidth={1.75} className="relative" />
    </button>
  );
}
