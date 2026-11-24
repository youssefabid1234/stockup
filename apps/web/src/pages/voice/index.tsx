/**
 * Voix — two modes, switched in the header (?mode=command):
 *  - Appel (conversation): two-track push-to-talk lab on WS /ai/voice (below).
 *  - Commande (un tour): single-turn voice commands on POST /ai/command, see ./command.tsx.
 *
 * Appel: two-track push-to-talk lab on WS /ai/voice.
 * Hold Space (or the big button) to speak as the caller; the agent answers with streamed text, tool calls and audio.
 * Per-turn latency chips + running average; live ERP writes of the voice agent on the right.
 */
import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useUrlState } from "@/lib/url-state";
import { Ear, MicOff, Mic, RotateCcw, Send, VolumeX } from "lucide-react";
import { useHandsFree } from "@/features/assistant/useHandsFree";
import { cn } from "@/lib/cn";
import { Button, Dot, IconButton, Input, Kbd, Page, PageHeader, Spinner, Tabs } from "@/ui";
import { useVoiceSession, type Activity, type Conn } from "@/features/assistant/useVoiceSession";
import { CallerBar, CallerForm } from "./caller";
import { CommandMode } from "./command";
import { LiveActivity } from "./live-activity";
import { MetricsBar } from "./metrics";
import { LevelBars, Timeline } from "./timeline";

const isTypingTarget = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
};

const STATE_LABEL: Record<Activity, string> = { idle: "Ready", recording: "Registration", thinking: "Agent's thinking", speaking: "Agent's talking." };

type Mode = "call" | "command";
const MODES: { id: Mode; label: string }[] = [
  { id: "call", label: "Call" },
  { id: "command", label: "Order" },
];

export default function VoicePage() {
  const [modeParam, setModeParam] = useUrlState("mode", "", { keepPage: true });
  const mode: Mode = modeParam === "command" ? "command" : "call";
  // Two modes = two header tabs: "Appel" (conversation over the WS session) and "Commande" (one stateless turn).
  const modeSwitch = <Tabs<Mode> value={mode} items={MODES} onChange={(m) => setModeParam(m === "command" ? m : "")} />;
  // Each mode owns its connection (WS session vs one POST per command): only the visible one is mounted.
  return mode === "command" ? <CommandMode modeSwitch={modeSwitch} /> : <CallMode modeSwitch={modeSwitch} />;
}

function CallMode({ modeSwitch }: { modeSwitch: ReactNode }) {
  const v = useVoiceSession();
  const vRef = useRef(v);
  vRef.current = v;
  const [text, setText] = useState("");
  const spaceDown = useRef(false);
  // team 12 (Youssef): hands-free = talk like on the phone (no key); OFF by default (Space) to save credits while testing, turn it on for the demo; remembered per browser
  const [handsFree, setHandsFree] = useState(() => { try { return localStorage.getItem("voice.handsFree") === "1"; } catch { return false; } });
  const toggleHandsFree = () => setHandsFree((on) => { try { localStorage.setItem("voice.handsFree", on ? "0" : "1"); } catch { /* private mode */ } return !on; });
  const listening = useHandsFree(v, handsFree && v.conn === "ready" && !!v.caller, spaceDown);

  // Space = push-to-talk (outside text fields), Esc = stop playback.
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      if (e.code === "Space" && !isTypingTarget(e.target) && !e.metaKey && !e.ctrlKey && !e.altKey) {
        e.preventDefault();
        if (e.repeat || spaceDown.current) return;
        spaceDown.current = true;
        void vRef.current.startTalking();
      } else if (e.key === "Escape") {
        vRef.current.stopPlayback();
      }
    };
    const up = (e: KeyboardEvent) => {
      if (e.code !== "Space" || !spaceDown.current) return;
      e.preventDefault();
      spaceDown.current = false;
      vRef.current.stopTalking();
    };
    const blur = () => {
      if (spaceDown.current) { spaceDown.current = false; vRef.current.stopTalking(); }
    };
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
    v.sendText(text);
    setText("");
  };

  const connected = v.conn === "ready";
  const ready = connected && !!v.caller; // team 12: no talking before the caller is identified

  return (
    <Page>
      <PageHeader
        title="Voice"
        meta={<ConnState conn={v.conn} />}
        tabs={modeSwitch}
        actions={
          <>
            {/* Active providers (not filters): informative chips, only where there is room. */}
            {v.providers ? (
              <div className="hidden items-center gap-1 xl:flex">
                <Provider k="llm" v={v.providers.llm} />
                <Provider k="stt" v={v.providers.stt} />
                <Provider k="tts" v={v.providers.tts} />
              </div>
            ) : null}
            {v.activity === "speaking" ? <Button size="sm" variant="ghost" icon={VolumeX} kbd="Esc" onClick={v.stopPlayback}>Cut</Button> : null}
            <Button size="sm" variant={handsFree ? "primary" : "default"} icon={Ear} onClick={toggleHandsFree} aria-pressed={handsFree}>
              Hands-free
            </Button>
            <Button size="sm" icon={RotateCcw} onClick={v.reset} disabled={!ready}>Restart call</Button>
          </>
        }
      />
      <div className="flex min-h-0 flex-1">
        <section className="flex min-w-0 flex-1 flex-col">
          {v.caller ? (
            <>
              <CallerBar caller={v.caller} onHangUp={v.endCall} />
              <MetricsBar turns={v.turns} />
              <Timeline turns={v.turns} activity={v.activity} level={v.level} />
            </>
          ) : (
            <div className="flex min-h-0 flex-1 overflow-y-auto px-5 py-6">
              <CallerForm disabled={!connected} pending={v.callerPending} onStart={v.identifyCaller} />
            </div>
          )}

          {v.mic === "denied" || v.mic === "unsupported" ? (
            <div className="flex shrink-0 items-center gap-2 border-t border-border bg-warning/[.08] px-5 py-2 text-[12px]">
              <MicOff size={14} strokeWidth={1.75} className="shrink-0 text-warning" />
              <span>
                {v.mic === "denied"
                  ? "Microphone access is blocked. Allow microphone access in your browser settings, or type what the caller says."
                  : "The microphone needs localhost or HTTPS. Type the caller's words instead."}
              </span>
            </div>
          ) : null}

          <div className="flex shrink-0 items-center gap-4 border-t border-border px-5 py-3">
            <TalkButton activity={v.activity} disabled={!ready} onDown={() => void v.startTalking()} onUp={v.stopTalking} />
            <div className="flex shrink-0 flex-col gap-1 xl:w-[180px]">
              <span className={cn("flex items-center gap-1.5 text-[13px] font-medium", v.activity !== "idle" && "text-violet")}>
                {v.activity === "thinking" ? <Spinner size={12} /> : v.activity !== "idle" ? <Dot tone="violet" pulse /> : null}
                {ready ? (listening && v.activity === "idle" ? "Listening" : STATE_LABEL[v.activity]) : connected ? "Choose a caller" : v.conn === "connecting" ? "Connecting…" : "Offline"}
              </span>
              {v.activity === "recording" ? (
                <LevelBars level={v.level} />
              ) : listening ? (
                <span className="hidden items-center gap-1 text-[11.5px] text-muted-foreground xl:flex">Hands-free · speak to interrupt</span>
              ) : (
                <span className="hidden items-center gap-1 text-[11.5px] text-muted-foreground xl:flex"><Kbd>Space</Kbd> Hold to talk</span>
              )}
            </div>
            <form onSubmit={submit} className="flex min-w-0 flex-1 items-center gap-2">
              <Input
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Escape") (e.target as HTMLInputElement).blur(); }}
                placeholder="Or type the caller's sentence..."
                disabled={!ready}
                className="min-w-0 flex-1"
              />
              <IconButton type="submit" icon={Send} label="Send" variant="default" disabled={!ready || !text.trim()} />
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

function ConnState({ conn }: { conn: Conn }) {
  return (
    <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
      <Dot tone={conn === "ready" ? "success" : conn === "connecting" ? "warning" : "destructive"} pulse={conn === "connecting"} />
      {conn === "ready" ? "Connected" : conn === "connecting" ? "Connecting…" : "AI service unavailable · reconnecting…"}
    </span>
  );
}

function Provider({ k, v }: { k: string; v: string }) {
  return (
    <span className="inline-flex h-[20px] max-w-[220px] items-center gap-1 truncate rounded-[3px] border border-border px-1.5 font-mono text-[10.5px]" title={`${k} : ${v}`}>
      <span className="text-muted-foreground">{k}</span>
      <span className="truncate text-secondary-foreground">{v}</span>
    </span>
  );
}

function TalkButton({ activity, disabled, onDown, onUp }: { activity: Activity; disabled: boolean; onDown: () => void; onUp: () => void }) {
  const rec = activity === "recording";
  const held = useRef(false);
  return (
    <button
      type="button"
      disabled={disabled}
      aria-label="Hold to talk"
      aria-pressed={rec}
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
      className={cn(
        "relative flex h-14 w-14 shrink-0 select-none items-center justify-center rounded-full border transition-[transform,background-color,border-color] duration-100",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet/70 disabled:opacity-40",
        rec
          ? "scale-95 border-violet bg-violet text-primary-foreground"
          : "border-violet/40 bg-violet/10 text-violet hover:border-violet hover:bg-violet/15",
      )}
      style={{ touchAction: "none" }}
    >
      {rec ? <span className="absolute inset-0 animate-ping rounded-full bg-violet/30" aria-hidden /> : null}
      <Mic size={22} strokeWidth={1.75} className="relative" />
    </button>
  );
}
