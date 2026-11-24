/**
 * Team 12 (Amine K.): the wholesaler's office behind Lucie, synthesized in the browser (Web Audio, no audio file):
 * a low room tone and, now and then, a desk phone ringing in another office. It fades down while the agent's answer
 * is spoken (`duck(true)`, on the server's agent_answer_start) and comes back when she stops, so it never covers
 * her voice. The keyboard while she looks something up comes from the server, in the agent's own audio.
 */
const AMBIENT = 1; // master level while waiting / listening
const DUCKED = 0.15; // master level while the answer is spoken
const ROOM = 0.035; // room tone
const RING = 0.03; // a distant desk phone

export class OfficeAmbiance {
  private ctx: AudioContext | undefined;
  private master: GainNode | undefined;
  private timer: number | undefined;

  start() {
    if (this.ctx) return;
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    this.ctx = ctx;
    void ctx.resume().catch(() => { /* autoplay: resumes on the next click */ });
    const master = ctx.createGain();
    master.gain.setValueAtTime(0, ctx.currentTime);
    master.gain.linearRampToValueAtTime(AMBIENT, ctx.currentTime + 1.5);
    master.connect(ctx.destination);
    this.master = master;

    // Room tone: brown noise through a low-pass filter (ventilation, a far conversation), looped.
    const seconds = 4;
    const buf = ctx.createBuffer(1, ctx.sampleRate * seconds, ctx.sampleRate);
    const d = buf.getChannelData(0);
    let last = 0;
    for (let i = 0; i < d.length; i++) {
      last = (last + 0.02 * (Math.random() * 2 - 1)) / 1.02;
      d[i] = last * 3.5;
    }
    const noise = ctx.createBufferSource();
    noise.buffer = buf;
    noise.loop = true;
    const lp = ctx.createBiquadFilter();
    lp.type = "lowpass";
    lp.frequency.value = 500;
    const room = ctx.createGain();
    room.gain.value = ROOM;
    noise.connect(lp).connect(room).connect(master);
    noise.start();

    this.timer = window.setTimeout(() => this.ringLoop(), 3000 + Math.random() * 4000);
  }

  /** A phone rings somewhere every 8-20 s. */
  private ringLoop() {
    this.ring();
    this.timer = window.setTimeout(() => this.ringLoop(), 8000 + Math.random() * 12000);
  }

  /** A desk phone two offices away: 1 or 2 rings, each two short warbling bursts, muffled and panned. */
  private ring() {
    const ctx = this.ctx;
    const master = this.master;
    if (!ctx || !master || ctx.state !== "running") return;
    const out = ctx.createGain();
    out.gain.value = RING * (0.6 + Math.random() * 0.4);
    const muffle = ctx.createBiquadFilter();
    muffle.type = "lowpass";
    muffle.frequency.value = 1800;
    const pan = ctx.createStereoPanner();
    pan.pan.value = Math.random() * 1.6 - 0.8;
    muffle.connect(out).connect(pan).connect(master);
    const t0 = ctx.currentTime + 0.05;
    const rings = 1 + Math.floor(Math.random() * 2);
    let end = t0;
    for (let r = 0; r < rings; r++) {
      for (const offset of [0, 0.45]) {
        const start = t0 + r * 3 + offset;
        const burst = ctx.createGain();
        burst.gain.setValueAtTime(0, start);
        burst.gain.linearRampToValueAtTime(1, start + 0.01);
        burst.gain.setValueAtTime(1, start + 0.33);
        burst.gain.linearRampToValueAtTime(0, start + 0.38);
        burst.connect(muffle);
        // the bell's warble: two tones, amplitude-modulated at ~20 Hz
        const am = ctx.createGain();
        am.gain.value = 0.5;
        const lfo = ctx.createOscillator();
        lfo.type = "square";
        lfo.frequency.value = 20;
        const lfoDepth = ctx.createGain();
        lfoDepth.gain.value = 0.5;
        lfo.connect(lfoDepth).connect(am.gain);
        am.connect(burst);
        for (const f of [1300, 1650]) {
          const osc = ctx.createOscillator();
          osc.type = "triangle";
          osc.frequency.value = f;
          osc.connect(am);
          osc.start(start);
          osc.stop(start + 0.4);
        }
        lfo.start(start);
        lfo.stop(start + 0.4);
        end = start + 0.4;
      }
    }
    window.setTimeout(() => { try { pan.disconnect(); } catch { /* closed */ } }, (end - ctx.currentTime + 0.5) * 1000);
  }

  /** Fade under the agent's answer (on), back up when she stops (off). */
  duck(on: boolean) {
    const ctx = this.ctx;
    const master = this.master;
    if (!ctx || !master) return;
    const now = ctx.currentTime;
    master.gain.cancelScheduledValues(now);
    master.gain.setValueAtTime(master.gain.value, now);
    master.gain.linearRampToValueAtTime(on ? DUCKED : AMBIENT, now + (on ? 0.3 : 0.8));
  }

  stop() {
    window.clearTimeout(this.timer);
    const ctx = this.ctx;
    const master = this.master;
    this.ctx = undefined;
    this.master = undefined;
    if (!ctx || !master) return;
    master.gain.cancelScheduledValues(ctx.currentTime);
    master.gain.setValueAtTime(master.gain.value, ctx.currentTime);
    master.gain.linearRampToValueAtTime(0, ctx.currentTime + 0.4);
    window.setTimeout(() => { void ctx.close().catch(() => { /* already closed */ }); }, 500);
  }
}
