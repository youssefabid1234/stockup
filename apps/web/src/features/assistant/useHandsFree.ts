/**
 * Team 12 (Youssef) · hands-free mode of the Voix page: the mic stays open, speech start / end are detected (vad.ts)
 * and drive the same startTalking / stopTalking as the Space key, so the server side does not change at all.
 * Talking while the agent speaks (or thinks) interrupts it, exactly like pressing Space does today (barge-in).
 * Space keeps working: while it is held, detection pauses.
 */
import { useEffect, useRef, useState, type MutableRefObject } from "react";
import { DEFAULT_VAD, Vad } from "./vad";
import type { Activity } from "./useVoiceSession";

export interface HandsFreeTarget {
  activity: Activity;
  ensureMic: () => Promise<MediaStream | undefined>;
  readRms: () => number | undefined;
  startTalking: () => Promise<void>;
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
        if (ev === "start" && !owns.current) {
          owns.current = true;
          void t.startTalking();
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
