/**
 * Team 12 (Youssef) · hands-free mode of the Voix page: the mic stays open, speech start / end are detected (vad.ts)
 * and drive the same startTalking / stopTalking as the Space key, so the server side does not change at all.
 * Talking while the agent speaks (or thinks) interrupts it, exactly like pressing Space does today (barge-in).
 * Space keeps working: while it is held, detection pauses.
 */
import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { DEFAULT_VAD, Vad } from "./vad";
import type { Activity } from "./useVoiceSession";

const CHECK_MS = 900; // team 12: how long a sound over Lucie's voice is checked
const CONFIRM_LOUD_MS = 450; // voiced this long within it = a real interruption

export interface HandsFreeTarget {
  activity: Activity;
  ensureMic: () => Promise<MediaStream | undefined>;
  readRms: () => number | undefined;
  startTalking: (opts?: { tentative?: boolean }) => Promise<void>;
  confirmTalking?: () => void;
  cancelTalking?: () => void;
  stopTalking: (opts?: { quiet?: boolean }) => void;
  nudge?: () => void;
  turns?: { length: number };
}

/** After the agent's answer, this long without a word from the caller → one short line (« Vous êtes toujours là ? »),
 * once per silence (the voice-agent guides: ask once after 10-15 s, never nag). */
export const NUDGE_AFTER_MS = 10_000

const TICK_MS = 30;

/** Returns true while the page is listening hands-free. */
export function useHandsFree(target: HandsFreeTarget, enabled: boolean, spaceDown: MutableRefObject<boolean>): boolean {
  const ref = useRef(target);
  ref.current = target;
  const owns = useRef(false); // the current recording was started by detection (not by Space)
  const [listening, setListening] = useState(false);

  useEffect(() => {
    if (!enabled) return undefined;
    let stopped = false;
    let timer: ReturnType<typeof setInterval> | undefined;
    const vad = new Vad(DEFAULT_VAD);
    let idleSince: number | null = null;
    let nudged = false;
    let check: { at: number; loud: number; level: number } | null = null;
    void (async () => {
      if (!(await ref.current.ensureMic()) || stopped) return;
      setListening(true);
      timer = setInterval(() => {
        const t = ref.current;
        if (spaceDown.current) { vad.reset(); return; } // push-to-talk has priority
        const rms = t.readRms();
        if (rms === undefined) return;
        const now = performance.now();
        const ev = vad.feed(rms, now, t.activity === "speaking");
        // silence after the agent's answer: one nudge, then wait (reset as soon as anyone speaks)
        if (t.activity !== "idle" || vad.isSpeaking) { idleSince = null; nudged = vad.isSpeaking ? false : nudged; }
        else if (idleSince === null) idleSince = now;
        else if (!nudged && (t.turns?.length ?? 0) > 0 && now - idleSince > NUDGE_AFTER_MS && t.nudge) { nudged = true; t.nudge(); }
        // team 12 (Youssef): over Lucie's voice, a sound is first checked: real speech (loud ≥ CONFIRM_LOUD_MS within
        // CHECK_MS) interrupts her; a click, a cough, a short noise does not (her voice dips, then comes back)
        if (check) {
          if (rms >= check.level) check.loud += TICK_MS;
          if (check.loud >= CONFIRM_LOUD_MS) { check = null; t.confirmTalking?.(); }
          else if (now - check.at >= CHECK_MS || ev === "end" || ev === "cancel") {
            check = null;
            owns.current = false;
            vad.reset();
            t.cancelTalking?.();
            return;
          }
        }
        if (ev === "start" && !owns.current) {
          owns.current = true;
          if (t.activity === "speaking" && t.confirmTalking) {
            check = { at: now, loud: 0, level: Math.max(0.02, rms * 0.5) };
            void t.startTalking({ tentative: true });
          } else void t.startTalking();
        } else if ((ev === "end" || ev === "cancel") && owns.current) {
          owns.current = false;
          t.stopTalking({ quiet: true });
        }
      }, TICK_MS);
    })();
    return () => {
      stopped = true;
      if (timer) clearInterval(timer);
      setListening(false);
      if (owns.current) { owns.current = false; ref.current.stopTalking({ quiet: true }); }
    };
  }, [enabled, spaceDown]);

  return listening;
}
