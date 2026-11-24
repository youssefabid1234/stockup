import { OutboundCalls } from "./outbound";
import { PlannedCalls } from "./planned";
import { AgentNotebook } from "./notebook";
/**
 * Voix — two modes, switched in the header (?mode=command):
 *  - Appel (conversation): two-track push-to-talk lab on WS /ai/voice (below).
 *  - Commande (un tour): single-turn voice commands on POST /ai/command, see ./command.tsx.
 *
 * Appel: a messaging-app call view on WS /ai/voice (team 12: chat.tsx, WhatsApp-like).
 * Hold Space (or the big button) to speak as the caller; the agent answers with streamed text, tool calls and audio.
 * Per-turn latency chips + running average; live ERP writes of the voice agent on the right.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { OfficeAmbiance } from "@/features/assistant/ambiance";
import { useUrlState } from "@/lib/url-state";
import { MicOff } from "lucide-react";
import { useHandsFree } from "@/features/assistant/useHandsFree";
import { cn } from "@/lib/cn";
import { Dot, Page, PageHeader, Tabs } from "@/ui";
import { useVoiceSession, type Conn } from "@/features/assistant/useVoiceSession";
import { CallerForm } from "./caller";
import { ChatHeader, ChatMessages, Composer, QuickReplies, WALLPAPER } from "./chat";
import { CommandMode } from "./command";
import { LiveActivity } from "./live-activity";
import { MetricsBar } from "./metrics";

const isTypingTarget = (t: EventTarget | null) => {
  const el = t as HTMLElement | null;
  return !!el && (el.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName));
};

type Mode = "call" | "command";
const MODES: { id: Mode; label: string }[] = [
  { id: "call", label: "Appel" },
  { id: "command", label: "Commande" },
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
  const spaceDown = useRef(false);
  // team 12 (Youssef): hands-free = talk like on the phone (no key); OFF by default (Space) to save credits while testing, turn it on for the demo; remembered per browser
  const [handsFree, setHandsFree] = useState(() => { try { return localStorage.getItem("voice.handsFree") === "1"; } catch { return false; } });
  const toggleHandsFree = () => setHandsFree((on) => { try { localStorage.setItem("voice.handsFree", on ? "0" : "1"); } catch { /* private mode */ } return !on; });
  const listening = useHandsFree(v, handsFree && v.conn === "ready" && !!v.caller, spaceDown);
  // team 12 (Amine K.): office background during the call (phones ringing far away), faded under the agent's answer
  const [ambiance, setAmbiance] = useState(() => { try { return localStorage.getItem("voice.ambiance") !== "0"; } catch { return true; } });
  const toggleAmbiance = () => setAmbiance((on) => { try { localStorage.setItem("voice.ambiance", on ? "0" : "1"); } catch { /* private mode */ } return !on; });
  const office = useRef<OfficeAmbiance>();
  const inCall = !!v.caller;
  useEffect(() => {
    if (ambiance && inCall) {
      office.current ??= new OfficeAmbiance();
      office.current.start();
    } else {
      office.current?.stop();
      office.current = undefined;
    }
  }, [ambiance, inCall]);
  useEffect(() => { office.current?.duck(v.answering); }, [v.answering]);
  useEffect(() => () => office.current?.stop(), []);
  // team 12 (Youssef): call timer of the chat header (from the moment the caller is identified)
  const [callStart, setCallStart] = useState<number>();
  useEffect(() => {
    if (!v.caller) setCallStart(undefined);
    else setCallStart((s) => s ?? Date.now());
  }, [v.caller]);

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

  const connected = v.conn === "ready";
  const ready = connected && !!v.caller; // team 12: no talking before the caller is identified

  return (
    <Page>
      <PageHeader
        title="Voix"
        meta={<ConnState conn={v.conn} />}
        tabs={modeSwitch}
        actions={
          v.providers ? (
            /* Active providers (not filters): informative chips, only where there is room. */
            <div className="hidden items-center gap-1 xl:flex">
              <Provider k="llm" v={v.providers.llm} />
              <Provider k="stt" v={v.providers.stt} />
              <Provider k="tts" v={v.providers.tts} />
            </div>
          ) : null
        }
      />
      <div className="flex min-h-0 flex-1">
        <section className="flex min-w-0 flex-1 flex-col">
          {v.caller ? (
            <>
              <ChatHeader
                caller={v.caller}
                since={callStart}
                activity={v.activity}
                listening={listening}
                handsFree={handsFree}
                onToggleHandsFree={toggleHandsFree}
                ambiance={ambiance}
                onToggleAmbiance={toggleAmbiance}
                onStopPlayback={v.stopPlayback}
                onRestart={v.caller.outboundId ? undefined : v.reset}
                onHangUp={v.endCall}
              />
              <MetricsBar turns={v.turns} />
              <ChatMessages turns={v.turns} activity={v.activity} level={v.level} caller={v.caller} />
              <QuickReplies turns={v.turns} disabled={!ready} onPick={v.sendText} />
            </>
          ) : (
            <div className={cn("flex min-h-0 flex-1 flex-col items-center overflow-y-auto px-5 py-8", WALLPAPER)}>
              <div className="flex w-full max-w-[560px] flex-col items-center gap-4">
                <img src="/brand/fournil-occitan.svg" alt="Le Fournil Occitan" className="h-20 w-20 rounded-full shadow-md" />
                <div className="text-center">
                  <div className="text-[18px] font-semibold text-[#111b21] dark:text-[#e9edef]">Le Fournil Occitan</div>
                  <div className="text-[13px] text-[#667781] dark:text-[#8696a0]">Standard téléphonique · Lucie, assistante vocale</div>
                </div>
                <div className="w-full">
                  <CallerForm disabled={!connected} pending={v.callerPending} onStart={v.identifyCaller} />
                </div>
              </div>
            </div>
          )}

          {v.mic === "denied" || v.mic === "unsupported" ? (
            <div className="flex shrink-0 items-center gap-2 border-t border-border bg-warning/[.08] px-5 py-2 text-[12px]">
              <MicOff size={14} strokeWidth={1.75} className="shrink-0 text-warning" />
              <span>
                {v.mic === "denied"
                  ? "Micro refusé : autorisez-le dans les réglages du site (icône à gauche de l'adresse), puis réessayez. En attendant, tapez les phrases de l'appelant."
                  : "Micro indisponible dans ce navigateur (il faut localhost ou https). Tapez les phrases de l'appelant."}
              </span>
            </div>
          ) : null}

          <Composer
            ready={ready}
            activity={v.activity}
            listening={listening}
            level={v.level}
            onSend={v.sendText}
            onTalkDown={() => void v.startTalking()}
            onTalkUp={v.stopTalking}
          />
        </section>
        <aside className="flex w-[280px] shrink-0 flex-col overflow-y-auto border-l border-border bg-card xl:w-[320px] 2xl:w-[380px]">
          <AgentNotebook caller={v.caller} turns={v.turns} />
          <PlannedCalls ready={connected} busy={!!v.caller} pending={v.callerPending} />
          <OutboundCalls ready={connected} busy={!!v.caller} pending={v.callerPending}
            onAnswer={(outboundId) => v.identifyCaller({ outboundId })}
            error={v.lastError?.startsWith("Impossible de décrocher") ? v.lastError : undefined} />
          <div className="min-h-36 flex-1"><LiveActivity /></div>
        </aside>
      </div>
    </Page>
  );
}

function ConnState({ conn }: { conn: Conn }) {
  return (
    <span className="flex items-center gap-1.5 text-[12px] text-muted-foreground">
      <Dot tone={conn === "ready" ? "success" : conn === "connecting" ? "warning" : "destructive"} pulse={conn === "connecting"} />
      {conn === "ready" ? "Connecté" : conn === "connecting" ? "Connexion…" : "Service IA injoignable · nouvel essai…"}
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
