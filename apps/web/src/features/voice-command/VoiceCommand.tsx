/**
 * Global voice command: hold ⌥ Space (or press-and-hold the "Voix" button) on ANY page, say one command, release.
 * A compact HUD at the bottom center shows: level meter → transcript → ERP tool rows → one-line answer + "Ouvrir".
 * It auto-dismisses a few seconds after the answer; Esc closes it. On /voice the page shows the runs itself (no HUD).
 */
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Check, CircleAlert, Keyboard, Mic, MicOff, Send, Volume2, VolumeX, X } from "lucide-react";
import { cn } from "@/lib/cn";
import { buttonClass, Dot, IconButton, Input, Kbd, Spinner } from "@/ui";
import { LiveTranscript } from "@/features/assistant/LiveTranscript";
import { ToolRow } from "@/features/assistant/tools";
import {
  closeHud, isRecordingCommand, onCommandNavigate, openHud, sendCommandText, setSpeak, startCommand, stopCommand, useVoiceCommand,
  type CommandRun, type CommandState,
} from "./engine";
import { LevelMeter, RunLinks } from "./parts";

export const VOICE_COMMAND_HINT = "⌥ Espace";
const DISMISS_MS = 6_000;
const DISMISS_ERROR_MS = 9_000;
const onVoicePage = (path: string) => path === "/voice" || path.startsWith("/voice/");

/** Hold ⌥ Space anywhere = record a command (works inside inputs too: Option+Space would only type a nbsp). */
function useHoldToTalkShortcut() {
  useEffect(() => {
    let held = false;
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && e.altKey && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        if (e.repeat || held) return;
        held = true;
        void startCommand();
      } else if (e.key === "Escape" && !held) {
        closeHud();
      }
    };
    const up = (e: KeyboardEvent) => {
      if (!held || (e.code !== "Space" && e.key !== "Alt")) return;
      e.preventDefault();
      held = false;
      stopCommand();
    };
    const blur = () => { if (held) { held = false; stopCommand(); } };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    window.addEventListener("blur", blur);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
      window.removeEventListener("blur", blur);
    };
  }, []);
}

/** Mount once in the shell (inside the router). Registers the shortcut, opens what the user asked to see, renders the HUD. */
export function VoiceCommandProvider({ children }: { children?: ReactNode }) {
  useHoldToTalkShortcut();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const pathRef = useRef(pathname);
  pathRef.current = pathname;

  useEffect(() => onCommandNavigate((nav) => {
    if (!onVoicePage(pathRef.current)) navigate(nav.path);
  }), [navigate]);

  return (
    <>
      {children}
      {onVoicePage(pathname) ? null : <VoiceCommandHud />}
    </>
  );
}

/** Header button: mic · "Voix" · ⌥ Espace. Press and hold to talk; a short click opens the HUD (typed command). */
export function VoiceCommandButton({ className }: { className?: string }) {
  const s = useVoiceCommand();
  const held = useRef(false);
  const rec = s.phase === "recording";
  return (
    <button
      type="button"
      aria-label={`Commande vocale : maintenir pour parler (${VOICE_COMMAND_HINT})`}
      title={`Commande vocale : maintenez pour parler (${VOICE_COMMAND_HINT})`}
      aria-pressed={rec}
      onPointerDown={(e) => {
        if (e.button !== 0) return;
        e.currentTarget.setPointerCapture(e.pointerId);
        held.current = true;
        void startCommand();
      }}
      onPointerUp={() => { if (held.current) { held.current = false; stopCommand(); } }}
      onPointerCancel={() => { if (held.current) { held.current = false; stopCommand(); } }}
      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); openHud(); } }}
      onContextMenu={(e) => e.preventDefault()}
      className={cn(
        buttonClass({ variant: "ghost", size: "sm" }),
        "px-2 text-secondary-foreground",
        rec && "border-violet/40 bg-violet/10 text-violet hover:bg-violet/15",
        className,
      )}
      style={{ touchAction: "none" }}
    >
      {rec ? <Dot tone="violet" pulse /> : <Mic size={13} strokeWidth={1.75} className="shrink-0 text-violet" aria-hidden />}
      <span className="shell-label">Voix</span>
      <Kbd className="shell-kbd ml-0.5">{VOICE_COMMAND_HINT}</Kbd>
    </button>
  );
}

const PHASE_LABEL: Record<CommandState["phase"], string> = {
  idle: "Commande vocale", recording: "J'écoute…", working: "J'exécute…", done: "Fait", error: "Échec",
};

export function VoiceCommandHud() {
  const s = useVoiceCommand();
  const [hover, setHover] = useState(false);
  const run = s.runs.find((r) => r.id === s.current);
  const finished = s.phase === "done" || s.phase === "error";

  // Auto-dismiss after the answer (paused while hovered).
  useEffect(() => {
    if (!s.hudOpen || !finished || hover) return;
    const t = window.setTimeout(closeHud, s.phase === "error" ? DISMISS_ERROR_MS : DISMISS_MS);
    return () => window.clearTimeout(t);
  }, [s.hudOpen, finished, hover, s.phase, s.current]);

  if (!s.hudOpen) return null;
  const micBlocked = s.mic === "denied" || s.mic === "unsupported";
  const showInput = micBlocked || (s.phase === "idle" && !run);

  return (
    <div className="pointer-events-none fixed inset-x-0 bottom-5 z-50 flex justify-center px-4">
      <div
        role="status"
        aria-live="polite"
        onMouseEnter={() => setHover(true)}
        onMouseLeave={() => setHover(false)}
        className="pointer-events-auto w-full max-w-[560px] overflow-hidden rounded-[6px] border border-border bg-card shadow-pop animate-fade-in"
      >
        <div className="flex h-9 items-center gap-2 border-b border-border px-3">
          <PhaseIcon phase={s.phase} />
          <span className={cn("text-[12.5px] font-medium", s.phase === "error" ? "text-destructive" : s.phase === "idle" ? "text-foreground" : "text-violet")}>
            {PHASE_LABEL[s.phase]}
          </span>
          {s.phase === "recording" ? <LevelMeter level={s.level} className="ml-1" /> : null}
          <span className="ml-auto flex items-center gap-1 text-[11px] text-muted-foreground">
            <Kbd>{VOICE_COMMAND_HINT}</Kbd>
            <span className="hidden sm:inline">maintenir</span>
          </span>
          <IconButton
            icon={s.speak ? Volume2 : VolumeX}
            label={s.speak ? "Couper la réponse vocale" : "Activer la réponse vocale"}
            size="sm"
            onClick={() => setSpeak(!s.speak)}
          />
          <IconButton icon={X} label="Fermer (Échap)" size="sm" onClick={closeHud} />
        </div>
        <div className="flex flex-col gap-2 px-3 py-2.5">
          {run ? <RunBody r={run} onNavigate={closeHud} /> : null}
          {micBlocked ? (
            <div className="flex items-start gap-2 text-[12px] text-secondary-foreground">
              <MicOff size={14} strokeWidth={1.75} className="mt-px shrink-0 text-warning" />
              {s.mic === "denied"
                ? "Micro refusé : autorisez-le dans les réglages du site (icône à gauche de l'adresse). En attendant, tapez la commande."
                : "Micro indisponible ici (il faut localhost ou https). Tapez la commande."}
            </div>
          ) : !run && s.phase === "idle" ? (
            <div className="text-[12px] text-muted-foreground">
              Maintenez <Kbd>{VOICE_COMMAND_HINT}</Kbd> et dites par ex. « crée une pré-commande pour Lemoine, 4 kilos de bar pour jeudi ».
            </div>
          ) : s.phase === "recording" && !run ? (
            <div className="flex items-center gap-2 text-[12px] text-muted-foreground"><Spinner size={12} />Ouverture du micro…</div>
          ) : null}
          {showInput ? <TypedCommand /> : null}
        </div>
      </div>
    </div>
  );
}

function PhaseIcon({ phase }: { phase: CommandState["phase"] }) {
  if (phase === "recording") return <Dot tone="violet" pulse />;
  if (phase === "working") return <Spinner size={12} className="text-violet" />;
  if (phase === "done") return <Check size={13} strokeWidth={2} className="text-violet" />;
  if (phase === "error") return <CircleAlert size={13} strokeWidth={1.75} className="text-destructive" />;
  return <Mic size={13} strokeWidth={1.75} className="text-violet" />;
}

/** transcript → tool rows → answer + links (also used by the Voix page history). */
export function RunBody({ r, onNavigate, compact }: { r: CommandRun; onNavigate?: () => void; compact?: boolean }) {
  return (
    <>
      {r.status === "recording" && !r.transcript ? (
        <div className="text-[12.5px] text-muted-foreground">Parlez, puis relâchez pour exécuter.</div>
      ) : r.status === "transcribing" && !r.transcript ? (
        <div className="flex items-center gap-2 text-[12.5px] text-muted-foreground"><Spinner size={12} />Transcription…</div>
      ) : (
        <div className="flex items-start gap-1.5 text-[13px] leading-[18px]">
          {r.typed ? <Keyboard size={12} strokeWidth={1.75} className="mt-[3px] shrink-0 text-muted-foreground" aria-label="tapé" /> : <Mic size={12} strokeWidth={1.75} className="mt-[3px] shrink-0 text-muted-foreground" aria-label="dit" />}
          <span className="text-secondary-foreground">
            « <LiveTranscript text={r.transcript || "…"} stable={r.stable} final={r.status !== "recording" && r.status !== "transcribing"} /> »
          </span>
        </div>
      )}
      {r.tools.length ? (
        <div className={cn("flex flex-col gap-1", compact && "max-w-[640px]")}>
          {r.tools.map((t) => <ToolRow key={t.id} t={t} onNavigate={onNavigate} />)}
        </div>
      ) : null}
      {r.error ? (
        <div className="flex items-start gap-1.5 text-[12.5px] text-destructive"><CircleAlert size={13} strokeWidth={1.75} className="mt-[2px] shrink-0" />{r.error}</div>
      ) : r.answer ? (
        <div className="flex flex-col gap-1">
          <div className="text-[13px] font-medium leading-[18px] text-foreground">{r.answer}</div>
          {r.status === "done" ? <RunLinks r={r} onNavigate={onNavigate} /> : null}
        </div>
      ) : r.status === "running" && r.tools.length === 0 ? (
        <div className="flex items-center gap-2 text-[12px] text-muted-foreground"><Spinner size={12} />Je réfléchis…</div>
      ) : null}
    </>
  );
}

function TypedCommand() {
  const [text, setText] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    sendCommandText(text);
    setText("");
  };
  return (
    <form onSubmit={submit} className="flex items-center gap-2">
      <Input
        autoFocus
        size="sm"
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Escape" && !isRecordingCommand()) closeHud(); }}
        placeholder="Ou tapez la commande…"
        className="min-w-0 flex-1"
      />
      <IconButton type="submit" icon={Send} label="Exécuter" size="sm" variant="default" disabled={!text.trim()} />
    </form>
  );
}
