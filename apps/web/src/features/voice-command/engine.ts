/**
 * Voice command engine — ONE utterance → POST /ai/command → one action on the ERP → one line (+ optional voice).
 * Module-level singleton (tiny external store), so the global HUD and the Voix page "Commande" mode share
 * the same recorder, the same run in progress and the same history.
 *
 *   hold (⌥ Space / button) → MediaRecorder chunks every 100 ms → WS /ai/voice/command?speak=1 (live transcription:
 *     `transcript` final:false while speaking) → release → audio_end
 *   typed → POST /ai/command?speak=1 (JSON), answered as SSE
 *   events (both): transcript → tool_call / tool_result / text → navigate? → speech? → done {timings} | error
 */
import { useSyncExternalStore } from "react";
import { MOCK_TTS_MIME, type CommandStreamEvent, type TurnTimings } from "@kit/shared";
import { AI_BASE } from "@/lib/api";
import type { ToolRun } from "@/features/assistant/tools";

export type CommandPhase = "idle" | "recording" | "working" | "done" | "error";
export type MicState = "unknown" | "granted" | "denied" | "unsupported";

export interface CommandRun {
  id: number;
  at: number;
  typed: boolean;
  status: "recording" | "transcribing" | "running" | "done" | "error";
  transcript: string;
  /** While recording/transcribing: the leading part of `transcript` made of final words (the rest may still change). */
  stable?: string;
  tools: ToolRun[];
  answer: string;
  error?: string;
  navigate?: { path: string; label?: string };
  timings?: TurnTimings;
  /** Client-side: key released → answer shown (or voice starts, when the voice reply is on). */
  perceivedMs?: number;
}

export interface CommandState {
  phase: CommandPhase;
  level: number; // mic level 0..1 while recording
  mic: MicState;
  speak: boolean; // voice reply on/off (persisted)
  hudOpen: boolean;
  current?: number; // id of the run shown in the HUD
  runs: CommandRun[]; // oldest first, capped
}

const SPEAK_KEY = "voice-command.speak";
const REC_MIME = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
const MIN_RECORDING_MS = 300; // shorter = an accidental tap, not a command
const MIC_IDLE_RELEASE_MS = 30_000; // keep the mic warm a little, then free it (browser "recording" dot goes away)

const readSpeak = () => {
  try { return localStorage.getItem(SPEAK_KEY) !== "0"; } catch { return true; }
};

let state: CommandState = { phase: "idle", level: 0, mic: "unknown", speak: readSpeak(), hudOpen: false, runs: [] };
const listeners = new Set<() => void>();
const navListeners = new Set<(nav: { path: string; label?: string }) => void>();

function set(patch: Partial<CommandState> | ((s: CommandState) => Partial<CommandState>)) {
  state = { ...state, ...(typeof patch === "function" ? patch(state) : patch) };
  listeners.forEach((l) => l());
}
function patchRun(id: number, fn: (r: CommandRun) => Partial<CommandRun>) {
  set((s) => ({ runs: s.runs.map((r) => (r.id === id ? { ...r, ...fn(r) } : r)) }));
}

export function useVoiceCommand(): CommandState {
  return useSyncExternalStore(
    (l) => { listeners.add(l); return () => listeners.delete(l); },
    () => state,
    () => state,
  );
}

/** Called when the user asked to SEE something ("montre-moi le stock de turbot"). The provider navigates. */
export function onCommandNavigate(fn: (nav: { path: string; label?: string }) => void) {
  navListeners.add(fn);
  return () => { navListeners.delete(fn); };
}

// ── Mic ──
let stream: MediaStream | undefined;
let releaseTimer: number | undefined;
let audioCtx: AudioContext | undefined;
let analyser: AnalyserNode | undefined;
let raf: number | undefined;
let recorder: MediaRecorder | undefined;
let recStartedAt = 0;
let pressed = false;
let seq = 0;
let inflight: AbortController | undefined; // typed command (POST)
let live: WebSocket | undefined; // spoken command (WS), from the press to `done`
let audioEl: HTMLAudioElement | undefined;
let releasedAt: number | undefined;

async function ensureMic(): Promise<MediaStream | undefined> {
  window.clearTimeout(releaseTimer);
  if (stream?.active) return stream;
  if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") { set({ mic: "unsupported" }); return undefined; }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
    set({ mic: "granted" });
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
    audioCtx = new Ctx();
    analyser = audioCtx.createAnalyser();
    analyser.fftSize = 512;
    audioCtx.createMediaStreamSource(stream).connect(analyser);
    return stream;
  } catch (e) {
    const name = (e as DOMException).name;
    set({ mic: name === "NotAllowedError" || name === "SecurityError" ? "denied" : "unsupported" });
    return undefined;
  }
}

function scheduleMicRelease() {
  window.clearTimeout(releaseTimer);
  releaseTimer = window.setTimeout(() => {
    if (recorder) return;
    stream?.getTracks().forEach((t) => t.stop());
    stream = undefined;
    void audioCtx?.close().catch(() => undefined);
    audioCtx = undefined;
    analyser = undefined;
  }, MIC_IDLE_RELEASE_MS);
}

function meter() {
  const an = analyser;
  if (!an) return;
  const buf = new Uint8Array(an.fftSize);
  const tick = () => {
    an.getByteTimeDomainData(buf);
    let sum = 0;
    for (const v of buf) { const x = (v - 128) / 128; sum += x * x; }
    set({ level: Math.min(1, Math.sqrt(sum / buf.length) * 4) });
    raf = requestAnimationFrame(tick);
  };
  tick();
}

// ── Playback ──
export function stopSpeaking() {
  try { window.speechSynthesis?.cancel(); } catch { /* ignore */ }
  audioEl?.pause();
  audioEl = undefined;
}

function markPerceived(id: number) {
  if (releasedAt == null) return;
  const ms = Math.round(performance.now() - releasedAt);
  releasedAt = undefined;
  patchRun(id, () => ({ perceivedMs: ms }));
}

function playSpeech(id: number, mime: string, base64: string, text: string) {
  stopSpeaking();
  if (mime === MOCK_TTS_MIME) {
    const synth = window.speechSynthesis;
    if (!synth || !text.trim()) return markPerceived(id);
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "fr-FR";
    const fr = synth.getVoices().find((v) => v.lang?.toLowerCase().startsWith("fr"));
    if (fr) u.voice = fr;
    u.rate = 1.1;
    u.onstart = () => markPerceived(id);
    synth.speak(u);
    return;
  }
  const bytes = Uint8Array.from(atob(base64), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(new Blob([bytes], { type: mime }));
  const el = new Audio(url);
  audioEl = el;
  el.onplaying = () => markPerceived(id);
  el.onended = el.onerror = () => { URL.revokeObjectURL(url); if (audioEl === el) audioEl = undefined; };
  el.play().catch(() => markPerceived(id));
}

// ── Typed command: POST /command (spoken ones go through openLive below) ──
async function run(id: number, text: string) {
  inflight?.abort();
  const abort = new AbortController();
  inflight = abort;
  const speak = state.speak;
  let res: Response;
  try {
    res = await fetch(`${AI_BASE}/command${speak ? "?speak=1" : ""}`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "text/event-stream" },
      body: JSON.stringify({ text, actorName: "Commande vocale" }),
      signal: abort.signal,
    });
  } catch (e) {
    if ((e as Error).name === "AbortError") return;
    return fail(id, "Service IA injoignable (localhost:4100)");
  }
  if (!res.ok || !res.body) {
    let msg = `Service IA : erreur ${res.status}`;
    try { const j = await res.json(); if (j?.error?.message) msg = j.error.message; } catch { /* not JSON */ }
    return fail(id, msg);
  }

  const onEvent = commandEvents(id, speak);

  try {
    await readSSE(res.body, onEvent);
  } catch (e) {
    if ((e as Error).name !== "AbortError") fail(id, (e as Error).message);
  } finally {
    if (inflight === abort) inflight = undefined;
  }
}

/** Applies the command's events (SSE of POST /command or JSON messages of WS /voice/command) to run `id`. */
function commandEvents(id: number, speak: boolean) {
  let answer = "";
  return (e: CommandStreamEvent) => {
    switch (e.type) {
      case "transcript":
        if (e.final === false) {
          // Live partial: only while the words are still being heard.
          patchRun(id, (r) => (r.status === "recording" || r.status === "transcribing" ? { transcript: e.text, stable: e.stable ?? "" } : {}));
        } else {
          patchRun(id, () => ({ transcript: e.text, stable: undefined, status: "running" }));
        }
        break;
      case "tool_call":
        patchRun(id, (r) => ({ tools: [...r.tools, { id: e.call.id, name: e.call.name, args: e.call.arguments }] }));
        break;
      case "tool_result":
        patchRun(id, (r) => ({ tools: r.tools.map((t) => (t.id === e.callId ? { ...t, ok: e.ok, ms: e.ms, result: e.result } : t)) }));
        break;
      case "text":
        answer += e.delta;
        patchRun(id, () => ({ answer }));
        break;
      case "navigate":
        patchRun(id, () => ({ navigate: { path: e.path, label: e.label } }));
        navListeners.forEach((l) => l({ path: e.path, label: e.label }));
        break;
      case "speech":
        playSpeech(id, e.mime, e.audio, answer);
        break;
      case "done":
        answer = e.message.content || answer;
        patchRun(id, () => ({ answer, status: "done", timings: e.timings }));
        if (!speak) markPerceived(id);
        if (state.current === id) set({ phase: "done" });
        break;
      case "error":
        fail(id, e.message);
        break;
    }
  };
}

async function readSSE(body: NonNullable<Response["body"]>, onEvent: (e: CommandStreamEvent) => void) {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += value;
    let i: number;
    while ((i = buf.search(/\r?\n\r?\n/)) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i).replace(/^\r?\n\r?\n/, "");
      const data = block.split(/\r?\n/).filter((l) => l.startsWith("data:")).map((l) => l.slice(5).replace(/^ /, "")).join("\n");
      if (!data) continue;
      try { onEvent(JSON.parse(data) as CommandStreamEvent); } catch { /* malformed line */ }
    }
  }
}

function fail(id: number, message: string) {
  patchRun(id, () => ({ status: "error", error: message }));
  if (state.current === id) set({ phase: "error" });
}

const liveUrl = (speak: boolean) =>
  `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${AI_BASE}/voice/command${speak ? "?speak=1" : ""}`;

/** Opens WS /voice/command for run `id`: returns `send`, which queues until the socket is open. */
function openLive(id: number): (data: Blob | string) => void {
  dropLive();
  const sock = new WebSocket(liveUrl(state.speak));
  live = sock;
  const queue: (Blob | string)[] = [];
  const onEvent = commandEvents(id, state.speak);
  sock.onopen = () => queue.splice(0).forEach((d) => sock.send(d));
  sock.onmessage = (ev) => {
    try { onEvent(JSON.parse(ev.data as string) as CommandStreamEvent); } catch { /* malformed message */ }
  };
  sock.onclose = () => {
    if (live === sock) live = undefined;
    const r = state.runs.find((x) => x.id === id);
    if (r && r.status !== "done" && r.status !== "error") fail(id, "Service IA injoignable (WS /ai/voice/command)");
  };
  return (d) => (sock.readyState === WebSocket.OPEN ? sock.send(d) : queue.push(d));
}

/** Cancel the spoken command in progress (closing the socket cancels it server-side, STT stream included). */
function dropLive() {
  const sock = live;
  live = undefined;
  if (!sock) return;
  sock.onmessage = sock.onclose = null;
  sock.close();
}

function newRun(typed: boolean, transcript = ""): number {
  const id = ++seq;
  const r: CommandRun = { id, at: Date.now(), typed, status: typed ? "running" : "recording", transcript, tools: [], answer: "" };
  set((s) => ({ runs: [...s.runs, r].slice(-50), current: id, hudOpen: true }));
  return id;
}

// ── Public actions ──

/** Press: start recording (mic prompt the first time). */
export async function startCommand() {
  if (pressed) return;
  pressed = true;
  stopSpeaking();
  inflight?.abort();
  dropLive();
  set({ hudOpen: true, phase: "recording", level: 0 });
  const s = await ensureMic();
  if (!s) { pressed = false; set({ phase: "idle" }); return; }
  if (!pressed) { set({ phase: "idle" }); scheduleMicRelease(); return; } // released during the mic prompt
  const mime = REC_MIME.find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
  const rec = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
  const id = newRun(false);
  set({ phase: "recording" });
  recorder = rec;
  recStartedAt = performance.now();
  // Stream while the key is down: the server transcribes as the words come (partials shown in the HUD).
  const send = openLive(id);
  send(JSON.stringify({ type: "audio_start", mime: rec.mimeType || mime || "audio/webm" }));
  rec.ondataavailable = (e) => { if (e.data.size) send(e.data); };
  rec.onstop = () => {
    releasedAt = performance.now();
    send(JSON.stringify({ type: "audio_end" })); // the last chunk was sent just before
  };
  void audioCtx?.resume();
  rec.start(100); // a chunk every 100 ms
  meter();
}

/** Release: stop recording and send the utterance (or drop it if it was just a tap). */
export function stopCommand() {
  if (!pressed) return;
  pressed = false;
  if (raf) cancelAnimationFrame(raf);
  set({ level: 0 });
  const rec = recorder;
  recorder = undefined;
  scheduleMicRelease();
  if (!rec || rec.state === "inactive") return;
  const tooShort = performance.now() - recStartedAt < MIN_RECORDING_MS;
  const id = state.current;
  if (tooShort) {
    rec.onstop = null;
    rec.stop();
    dropLive();
    if (id != null) set((s) => ({ runs: s.runs.filter((r) => r.id !== id), current: undefined, phase: "idle" }));
    return;
  }
  rec.stop();
  if (id != null) patchRun(id, () => ({ status: "transcribing" }));
  set({ phase: "working" });
}

/** Typed command (debug, or mic denied). */
export function sendCommandText(text: string) {
  const v = text.trim();
  if (!v) return;
  stopSpeaking();
  const id = newRun(true, v);
  set({ phase: "working" });
  releasedAt = performance.now();
  void run(id, v);
}

export function openHud() { set({ hudOpen: true }); }

/** Esc / close: hide the HUD, cancel a recording, stop the voice. The run in flight keeps going (it is an ERP action). */
export function closeHud() {
  if (pressed) {
    pressed = false;
    if (raf) cancelAnimationFrame(raf);
    const rec = recorder;
    recorder = undefined;
    if (rec && rec.state !== "inactive") { rec.onstop = null; rec.stop(); }
    dropLive();
    const id = state.current;
    if (id != null) set((s) => ({ runs: s.runs.filter((r) => r.id !== id || r.status !== "recording") }));
    scheduleMicRelease();
  }
  stopSpeaking();
  set((s) => ({ hudOpen: false, level: 0, phase: s.phase === "recording" ? "idle" : s.phase }));
}

export function setSpeak(on: boolean) {
  try { localStorage.setItem(SPEAK_KEY, on ? "1" : "0"); } catch { /* ignore */ }
  if (!on) stopSpeaking();
  set({ speak: on });
}

export function clearCommandHistory() {
  set({ runs: [], current: undefined, phase: "idle" });
}

export const isRecordingCommand = () => pressed;
