/**
 * Team 12 (Youssef) · the call page as a messaging app (WhatsApp-like): brand header with the call status and timer,
 * bakery-doodle wallpaper, caller bubbles on the right (green) and agent bubbles on the left (white), typing dots
 * while the agent works, details (ERP checks, latency) folded under each answer, quick replies that follow the
 * agent's last question, and a rounded composer with the hold-to-talk microphone.
 * Colours: WhatsApp's palette in light and dark (the page's own look; the rest of the ERP keeps the design system).
 */
import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { CheckCheck, ChevronDown, CircleAlert, Ear, Keyboard, Mic, PhoneOff, RotateCcw, Send, VolumeX, Zap } from "lucide-react";
import type { CallerReady } from "@kit/shared";
import { cn } from "@/lib/cn";
import { LiveTranscript } from "@/features/assistant/LiveTranscript";
import { ToolRow } from "@/features/assistant/tools";
import type { Activity, VoiceTurn } from "@/features/assistant/useVoiceSession";
import { fmtMs, TurnChips } from "./metrics";
import { LevelBars } from "./timeline";

export const WALLPAPER =
  "bg-[#efeae2] bg-[url('/brand/fournil-wallpaper.svg')] dark:bg-[#0b141a] dark:bg-[url('/brand/fournil-wallpaper-dark.svg')] bg-[length:220px_220px]";
const HEADER = "bg-[#f0f2f5] dark:bg-[#202c33]";
const ACCENT = "bg-[#00a884] text-white hover:bg-[#008f72] dark:bg-[#00a884] dark:hover:bg-[#06cf9c]";
const hhmm = (at?: number) => (at ? new Date(at).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" }) : "");

// ── header ──

function useCallClock(since?: number) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!since) return undefined;
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, [since]);
  if (!since) return "";
  const s = Math.max(0, Math.floor((now - since) / 1000));
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export function ChatHeader(props: {
  caller: CallerReady;
  since?: number;
  activity: Activity;
  listening: boolean;
  handsFree: boolean;
  onToggleHandsFree: () => void;
  onStopPlayback: () => void;
  onRestart?: () => void;
  onHangUp: () => void;
}) {
  const { caller, activity, listening } = props;
  const clock = useCallClock(props.since);
  const status =
    activity === "thinking" ? "écrit…" : activity === "speaking" ? "parle…" : activity === "recording" ? "vous écoute…" : listening ? "à l'écoute" : "en ligne";
  return (
    <header className={cn("flex shrink-0 items-center gap-3 border-b border-black/5 px-4 py-2.5 dark:border-white/5", HEADER)}>
      <img src="/brand/fournil-occitan.svg" alt="" className="h-10 w-10 shrink-0 rounded-full shadow-sm" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 truncate text-[15px] font-semibold text-[#111b21] dark:text-[#e9edef]">
          Lucie · Le Fournil Occitan
        </div>
        <div className="flex items-center gap-1.5 truncate text-[12.5px] text-[#667781] dark:text-[#8696a0]">
          <span className={cn(activity !== "idle" && "font-medium text-[#00a884]")}>{status}</span>
          {clock ? <span className="num">· appel {clock}</span> : null}
          <span className="truncate">· {caller.name}{caller.contactName ? ` (${caller.contactName})` : ""}</span>
        </div>
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        {activity === "speaking" ? (
          <RoundButton title="Couper la parole à l'agent (Échap)" onClick={props.onStopPlayback} icon={<VolumeX size={18} strokeWidth={1.9} />} />
        ) : null}
        <button
          type="button"
          onClick={props.onToggleHandsFree}
          aria-pressed={props.handsFree}
          aria-label="Mains libres"
          title="Mains libres : parlez sans touche, l'agent répond après une courte pause"
          className={cn(
            "flex h-9 items-center gap-1.5 rounded-full px-3 text-[12.5px] font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a884]/60",
            props.handsFree ? ACCENT : "bg-black/5 text-[#3b4a54] hover:bg-black/10 dark:bg-white/10 dark:text-[#d1d7db] dark:hover:bg-white/15",
          )}
        >
          <Ear size={16} strokeWidth={1.9} />
          <span className="hidden 2xl:inline">Mains libres</span>
        </button>
        {props.onRestart ? <RoundButton title="Recommencer l'appel" onClick={props.onRestart} icon={<RotateCcw size={17} strokeWidth={1.9} />} /> : null}
        <button
          type="button"
          onClick={props.onHangUp}
          aria-label="Raccrocher"
          title="Raccrocher (arrête tout : micro, agent, voix)"
          className="flex h-9 items-center gap-1.5 rounded-full bg-[#ea0038] px-3.5 text-[12.5px] font-semibold text-white transition-colors hover:bg-[#c8002f] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#ea0038]/50"
        >
          <PhoneOff size={16} strokeWidth={2} />
          <span className="hidden xl:inline">Raccrocher</span>
        </button>
      </div>
    </header>
  );
}

function RoundButton({ title, onClick, icon }: { title: string; onClick: () => void; icon: ReactNode }) {
  return (
    <button
      type="button"
      title={title}
      aria-label={title}
      onClick={onClick}
      className="flex h-9 w-9 items-center justify-center rounded-full text-[#54656f] transition-colors hover:bg-black/5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a884]/60 dark:text-[#aebac1] dark:hover:bg-white/10"
    >
      {icon}
    </button>
  );
}

// ── messages ──

export function ChatMessages({ turns, activity, level, caller }: { turns: VoiceTurn[]; activity: Activity; level: number; caller: CallerReady }) {
  const ref = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  useLayoutEffect(() => {
    const el = ref.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [turns, activity]);
  return (
    <div
      ref={ref}
      className={cn("min-h-0 flex-1 overflow-y-auto", WALLPAPER)}
      onScroll={(e) => {
        const el = e.currentTarget;
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
      }}
    >
      <div className="mx-auto flex w-full max-w-[920px] flex-col gap-1.5 px-[6%] py-4">
        <SystemChip>Aujourd'hui</SystemChip>
        <SystemChip tone="notice">
          📞 Appel de <b>{caller.name}</b>
          {caller.contactName ? ` · ${caller.contactName}` : ""} ·{" "}
          {caller.isNew
            ? "nouveau client, à valider par l'équipe"
            : caller.usedByAgent
              ? `fiche client chargée${caller.loadedMs != null ? ` en ${caller.loadedMs} ms` : ""}`
              : "fiche indisponible, l'agent cherchera le client"}
        </SystemChip>
        {turns.length === 0 ? (
          <SystemChip>
            Dites bonjour : maintenez <b>Espace</b> ou le micro, activez <b>Mains libres</b>, ou touchez une réponse rapide.
          </SystemChip>
        ) : null}
        {turns.map((t, i) => (
          <Turn key={t.id} t={t} last={i === turns.length - 1} activity={activity} level={level} />
        ))}
      </div>
    </div>
  );
}

function SystemChip({ children, tone }: { children: ReactNode; tone?: "notice" }) {
  return (
    <div className="my-1 flex justify-center">
      <span
        className={cn(
          "max-w-[85%] rounded-[8px] px-3 py-1.5 text-center text-[12px] leading-snug shadow-[0_1px_0.5px_rgba(11,20,26,.13)]",
          tone === "notice"
            ? "bg-[#ffeecd] text-[#54656f] dark:bg-[#182229] dark:text-[#ffd279]"
            : "bg-white/90 text-[#54656f] dark:bg-[#182229] dark:text-[#8696a0]",
        )}
      >
        {children}
      </span>
    </div>
  );
}

function Turn({ t, last, activity, level }: { t: VoiceTurn; last: boolean; activity: Activity; level: number }) {
  const c = t.caller;
  const a = t.agent;
  const agentStarted = !!(a.text || a.tools.length || a.error);
  const thinking = !a.done && !agentStarted && c.status === "final";
  return (
    <>
      {c.silent ? null : (
        <Bubble side="right" time={hhmm(c.at)} read={a.done || agentStarted}>
          {c.status === "recording" ? (
            <span className="flex items-center gap-2">
              <Mic size={14} strokeWidth={2} className="shrink-0 animate-pulse text-[#00a884]" />
              {c.text ? <LiveTranscript text={c.text} stable={c.stable} /> : <span className="text-[#667781] dark:text-[#8696a0]">Vous parlez…</span>}
              <LevelBars level={last ? level : 0} className="shrink-0" />
            </span>
          ) : c.status === "transcribing" ? (
            <span className="flex items-center gap-2 text-[#667781] dark:text-[#8696a0]">
              <Dots />
              {c.text ? <LiveTranscript text={c.text} stable={c.stable} /> : "Transcription…"}
            </span>
          ) : (
            <span className="flex items-start gap-1.5">
              {c.typed ? <Keyboard size={12} strokeWidth={1.75} className="mt-[4px] shrink-0 opacity-60" aria-label="tapé" /> : null}
              <span>{c.text || <span className="opacity-60">(rien entendu)</span>}</span>
            </span>
          )}
        </Bubble>
      )}
      {thinking ? (
        <Bubble side="left">
          <span className="flex h-5 items-center px-1" aria-label="L'agent écrit">
            <Dots />
          </span>
        </Bubble>
      ) : null}
      {agentStarted ? (
        <Bubble side="left" time={hhmm(a.at)} speaking={last && activity === "speaking"}>
          {a.text ? (
            <span className={cn("whitespace-pre-wrap", !a.done && "after:ml-0.5 after:inline-block after:h-3 after:w-[2px] after:animate-pulse after:bg-[#00a884] after:align-middle after:content-['']")}>
              {a.text}
            </span>
          ) : !a.error ? (
            <span className="flex h-5 items-center px-1"><Dots /></span>
          ) : null}
          {a.error ? (
            <span className="mt-1 flex items-start gap-1.5 text-[12.5px] text-[#ea0038]"><CircleAlert size={13} strokeWidth={1.9} className="mt-[2px] shrink-0" />{a.error}</span>
          ) : null}
          {a.interrupted ? <span className="mt-1 block text-[11.5px] italic text-[#667781] dark:text-[#8696a0]">Interrompu par l'appelant</span> : null}
          <Details t={t} />
        </Bubble>
      ) : null}
    </>
  );
}

/** ERP checks and latency, folded: one line under the answer, the detail on click. */
function Details({ t }: { t: VoiceTurn }) {
  const [open, setOpen] = useState(false);
  const tools = t.agent.tools;
  const total = t.perceivedMs ?? t.timings?.totalMs;
  if (!tools.length && total == null) return null;
  return (
    <div className="mt-1.5 border-t border-black/5 pt-1 dark:border-white/10">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        className="flex items-center gap-1.5 rounded-[6px] text-[11.5px] text-[#667781] hover:text-[#111b21] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a884]/60 dark:text-[#8696a0] dark:hover:text-[#e9edef]"
      >
        {tools.length ? <span>🔎 {tools.length} vérification{tools.length > 1 ? "s" : ""} dans l'ERP</span> : null}
        {total != null ? (
          <span className="flex items-center gap-0.5"><Zap size={11} strokeWidth={2} />{fmtMs(total)}</span>
        ) : null}
        <ChevronDown size={13} strokeWidth={2} className={cn("transition-transform", open && "rotate-180")} />
      </button>
      {open ? (
        <div className="mt-1.5 flex flex-col gap-1">
          {tools.map((tool) => <ToolRow key={tool.id} t={tool} className="w-full" />)}
          <TurnChips t={t} />
        </div>
      ) : null}
    </div>
  );
}

function Bubble(props: { side: "left" | "right"; time?: string; read?: boolean; speaking?: boolean; children: ReactNode }) {
  const right = props.side === "right";
  return (
    <div className={cn("flex animate-fade-in", right ? "justify-end" : "justify-start")}>
      <div
        className={cn(
          "relative max-w-[78%] rounded-[10px] px-2.5 pb-1.5 pt-1.5 text-[14px] leading-[1.38] text-[#111b21] shadow-[0_1px_0.5px_rgba(11,20,26,.13)] dark:text-[#e9edef]",
          right ? "rounded-tr-[3px] bg-[#d9fdd3] dark:bg-[#005c4b]" : "rounded-tl-[3px] bg-white dark:bg-[#202c33]",
          props.speaking && "ring-2 ring-[#00a884]/35",
        )}
      >
        {props.children}
        {props.time ? (
          <span className="float-right ml-2 mt-1 flex translate-y-[3px] items-center gap-0.5 text-[10.5px] text-[#667781] dark:text-[#8696a0]">
            {props.speaking ? <Speaking /> : null}
            <span className="num">{props.time}</span>
            {right ? <CheckCheck size={14} strokeWidth={2} className={props.read ? "text-[#53bdeb]" : ""} /> : null}
          </span>
        ) : null}
      </div>
    </div>
  );
}

function Dots() {
  return (
    <span className="inline-flex items-center gap-[3px]" aria-hidden>
      {[0, 150, 300].map((d) => (
        <span key={d} className="h-[6px] w-[6px] animate-bounce rounded-full bg-[#8696a0]" style={{ animationDelay: `${d}ms`, animationDuration: "1s" }} />
      ))}
    </span>
  );
}

function Speaking() {
  return (
    <span className="mr-1 inline-flex h-3 items-end gap-[2px]" aria-label="parle">
      {[0, 120, 240].map((d) => (
        <span key={d} className="w-[2px] animate-pulse rounded-full bg-[#00a884]" style={{ height: `${6 + (d / 120) * 3}px`, animationDelay: `${d}ms` }} />
      ))}
    </span>
  );
}

// ── quick replies + composer ──

const AFTER_QUESTION = ["Oui, c'est bon", "Non merci", "Vous pouvez répéter ?", "Attendez, je réfléchis"];
const TO_START = ["Comme d'habitude pour jeudi", "Il me faut 10 sacs de tradi", "Vous avez du tourage AOP ?", "C'est quoi mon prix pour la tradi ?"];
const TO_END = ["Oui, validez", "C'est tout, merci", "Au revoir, bonne journée"];

/** Suggestions that follow the conversation: after a question, the usual answers; after a confirmation, the goodbyes. */
export function quickReplies(turns: VoiceTurn[]): string[] {
  const lastAgent = [...turns].reverse().find((t) => t.agent.text)?.agent.text.trim() ?? "";
  if (!lastAgent) return TO_START;
  if (/\b(valid|confirm)\w*/i.test(lastAgent) && lastAgent.endsWith("?")) return TO_END;
  if (lastAgent.endsWith("?")) return AFTER_QUESTION;
  return [...TO_END.slice(1), TO_START[2]];
}

export function QuickReplies({ turns, disabled, onPick }: { turns: VoiceTurn[]; disabled: boolean; onPick: (text: string) => void }) {
  const items = quickReplies(turns);
  return (
    <div className={cn("flex shrink-0 flex-wrap gap-2 px-4 pb-1 pt-2", WALLPAPER)} role="toolbar" aria-label="Réponses rapides">
      {items.map((label) => (
        <button
          key={label}
          type="button"
          disabled={disabled}
          onClick={() => onPick(label)}
          className="shrink-0 rounded-full border border-[#00a884]/40 bg-white px-3 py-1.5 text-[13px] text-[#008069] shadow-[0_1px_0.5px_rgba(11,20,26,.13)] transition-colors hover:bg-[#f0faf7] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a884]/60 disabled:opacity-40 dark:border-[#00a884]/40 dark:bg-[#202c33] dark:text-[#00a884] dark:hover:bg-[#2a3942]"
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function Composer(props: {
  ready: boolean;
  activity: Activity;
  listening: boolean;
  level: number;
  onSend: (text: string) => void;
  onTalkDown: () => void;
  onTalkUp: () => void;
}) {
  const [text, setText] = useState("");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    props.onSend(text);
    setText("");
  };
  const rec = props.activity === "recording";
  const hint = !props.ready
    ? "Identifiez l'appelant pour commencer"
    : rec
      ? "Je vous écoute…"
      : props.listening
        ? "Mains libres : parlez, ou tapez un message"
        : "Tapez la phrase de l'appelant, ou maintenez Espace / le micro";
  return (
    <form onSubmit={submit} className={cn("flex shrink-0 items-center gap-2 px-3 py-2.5", HEADER)}>
      <div className="flex min-w-0 flex-1 items-center gap-2 rounded-full bg-white px-4 py-2 shadow-[0_1px_0.5px_rgba(11,20,26,.13)] dark:bg-[#2a3942]">
        {rec ? <LevelBars level={props.level} className="shrink-0" /> : null}
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Escape") (e.target as HTMLInputElement).blur(); }}
          placeholder={hint}
          disabled={!props.ready}
          aria-label="Message de l'appelant"
          className="min-w-0 flex-1 bg-transparent text-[14.5px] text-[#111b21] placeholder:text-[#8696a0] focus:outline-none disabled:opacity-60 dark:text-[#e9edef]"
        />
      </div>
      {text.trim() ? (
        <button type="submit" disabled={!props.ready} aria-label="Envoyer" className={cn("flex h-11 w-11 shrink-0 items-center justify-center rounded-full shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a884]/60 disabled:opacity-40", ACCENT)}>
          <Send size={19} strokeWidth={2} />
        </button>
      ) : (
        <HoldToTalk disabled={!props.ready} recording={rec} onDown={props.onTalkDown} onUp={props.onTalkUp} />
      )}
    </form>
  );
}

function HoldToTalk({ disabled, recording, onDown, onUp }: { disabled: boolean; recording: boolean; onDown: () => void; onUp: () => void }) {
  const held = useRef(false);
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label="Maintenir pour parler"
      aria-pressed={recording}
      title="Maintenir pour parler (ou Espace)"
      onPointerDown={(e) => {
        if (e.button !== 0) return;
        e.currentTarget.setPointerCapture(e.pointerId);
        held.current = true;
        onDown();
      }}
      onPointerUp={() => { if (held.current) { held.current = false; onUp(); } }}
      onPointerCancel={() => { if (held.current) { held.current = false; onUp(); } }}
      onKeyDown={(e) => { if (e.key === "Enter") e.preventDefault(); }}
      onContextMenu={(e) => e.preventDefault()}
      style={{ touchAction: "none" }}
      className={cn(
        "relative flex h-11 w-11 shrink-0 select-none items-center justify-center rounded-full shadow-sm transition-transform focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#00a884]/60 disabled:opacity-40",
        ACCENT,
        recording && "scale-110",
      )}
    >
      {recording ? <span className="absolute inset-0 animate-ping rounded-full bg-[#00a884]/40" aria-hidden /> : null}
      <Mic size={20} strokeWidth={2} className="relative" />
    </button>
  );
}
