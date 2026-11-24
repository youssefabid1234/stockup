/**
 * Team 12 (Youssef) · hands-free: detect when the caller starts and stops speaking, from the mic level alone.
 *
 * Real life: on the phone nobody holds a key. Lucie hears you start, waits for a short pause, then answers; if you
 * talk over her, she stops. Here: a small state machine fed with the mic loudness (RMS, 0..1) every ~30 ms.
 *
 *   silent ──(louder than the room for startMs)──► speaking ──(quiet for endMs)──► silent   (emits "start" / "end")
 *
 * - The room's noise floor is learned while silent (slow average), so a noisy room needs a louder voice.
 * - While the agent is audible (its voice may leak back into the mic despite echo cancellation), starting needs a
 *   louder and longer sound: a real interruption, not the agent's own echo (barge-in).
 * - A sound shorter than minSpeechMs (cough, click) is dropped: "cancel" instead of "end" when possible.
 * Pure (no browser API): tested with node --test.
 */

export interface VadOptions {
  startMs: number; // loud this long → speech started
  endMs: number; // quiet this long → speech ended (the pause before the agent answers)
  minSpeechMs: number; // shorter sounds are not an utterance
  minLevel: number; // absolute floor of the start threshold (RMS)
  ratio: number; // start threshold = max(minLevel, noise floor × ratio)
  bargeInRatio: number; // threshold multiplier while the agent is audible
  bargeInStartMs: number; // start duration while the agent is audible
}

export const DEFAULT_VAD: VadOptions = {
  startMs: 90,
  endMs: 650,
  minSpeechMs: 250,
  minLevel: 0.02,
  ratio: 3,
  bargeInRatio: 2.5,
  bargeInStartMs: 220,
};

export type VadEvent = "start" | "end" | "cancel" | null;

export class Vad {
  private speaking = false;
  private loudSince: number | null = null;
  private quietSince: number | null = null;
  private speechSince = 0;
  noiseFloor = 0.005;

  constructor(private readonly o: VadOptions = DEFAULT_VAD) {}

  get isSpeaking(): boolean {
    return this.speaking;
  }

  threshold(agentAudible = false): number {
    const base = Math.max(this.o.minLevel, this.noiseFloor * this.o.ratio);
    return agentAudible ? base * this.o.bargeInRatio : base;
  }

  /** Feed one level sample. Returns the event it triggers, if any. */
  feed(rms: number, now: number, agentAudible = false): VadEvent {
    if (!this.speaking) {
      const thr = this.threshold(agentAudible);
      if (rms >= thr) {
        this.loudSince ??= now;
        if (now - this.loudSince >= (agentAudible ? this.o.bargeInStartMs : this.o.startMs)) {
          this.speaking = true;
          this.speechSince = this.loudSince;
          this.loudSince = null;
          this.quietSince = null;
          return "start";
        }
      } else {
        this.loudSince = null;
        // learn the room only from quiet samples (slow, so a voice does not raise it)
        if (!agentAudible) this.noiseFloor = this.noiseFloor * 0.98 + Math.min(rms, this.o.minLevel) * 0.02;
      }
      return null;
    }
    // speaking: end after a pause (hysteresis: "quiet" is below 60 % of the start threshold)
    if (rms < this.threshold(false) * 0.6) {
      this.quietSince ??= now;
      if (now - this.quietSince >= this.o.endMs) {
        this.speaking = false;
        const spoke = this.quietSince - this.speechSince;
        this.quietSince = null;
        return spoke >= this.o.minSpeechMs ? "end" : "cancel";
      }
    } else {
      this.quietSince = null;
    }
    return null;
  }

  reset(): void {
    this.speaking = false;
    this.loudSince = null;
    this.quietSince = null;
  }
}
