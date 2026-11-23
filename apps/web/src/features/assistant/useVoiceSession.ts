/**
 * Push-to-talk voice session over WS /ai/voice (contract: VoiceClientMessage / VoiceServerMessage in @kit/shared).
 * Mic → MediaRecorder (webm/opus) chunks every 100 ms, streamed as binary frames between audio_start and audio_end:
 * the server transcribes them as they arrive and sends `transcript` final:false (live text) before the final one.
 * Agent audio: binary frames between agent_audio_start/end → one Blob → <audio>. Mock TTS → speechSynthesis (fr-FR).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { MOCK_TTS_MIME, type TurnTimings, type VoiceClientMessage, type VoiceServerMessage } from "@kit/shared";
import { AI_BASE } from "@/lib/api";
import { SegmentPlayer } from "./audio-player";
import type { ToolRun } from "./tools";

export type Conn = "connecting" | "ready" | "offline";
export type Activity = "idle" | "recording" | "thinking" | "speaking";
export type MicState = "unknown" | "granted" | "denied" | "unsupported";

export interface VoiceTurn {
  id: number;
  /** text: live while recording/transcribing (stable = its final words), definitive once status is "final". */
  caller: { text: string; stable?: string; at: number; status: "recording" | "transcribing" | "final"; typed?: boolean };
  agent: { text: string; at?: number; tools: ToolRun[]; done: boolean; error?: string; interrupted?: boolean };
  timings?: TurnTimings;
  /** Client-side: caller release → agent audio actually starts playing (or speech synthesis starts). */
  perceivedMs?: number;
}

export interface Providers { llm: string; stt: string; tts: string; sessionId: string }

const REC_MIME = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"];
const wsUrl = () => `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${AI_BASE}/voice`;

export function useVoiceSession() {
  const [conn, setConn] = useState<Conn>("connecting");
  const [activity, setActivity] = useState<Activity>("idle");
  const [mic, setMic] = useState<MicState>("unknown");
  const [providers, setProviders] = useState<Providers>();
  const [turns, setTurns] = useState<VoiceTurn[]>([]);
  const [level, setLevel] = useState(0);
  const [lastError, setLastError] = useState<string>();

  const ws = useRef<WebSocket>();
  const sessionId = useRef<string>();
  const alive = useRef(true);
  const turnSeq = useRef(0);
  const currentTurn = useRef<number>();
  // mic
  const stream = useRef<MediaStream>();
  const recorder = useRef<MediaRecorder>();
  const pressed = useRef(false);
  const audioCtx = useRef<AudioContext>();
  const analyser = useRef<AnalyserNode>();
  const raf = useRef<number>();
  // playback
  const player = useRef<SegmentPlayer>();
  const audioMime = useRef<string>();
  const discardAudio = useRef(false); // audio of an interrupted turn still draining
  const releasedAt = useRef<number>();
  const turnHasAudio = useRef(false);

  const patchTurn = useCallback((id: number | undefined, fn: (t: VoiceTurn) => VoiceTurn) => {
    if (id == null) return;
    setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)));
  }, []);

  const newTurn = useCallback((caller: VoiceTurn["caller"]) => {
    const id = ++turnSeq.current;
    const prev = currentTurn.current;
    currentTurn.current = id;
    turnHasAudio.current = false;
    audioMime.current = undefined;
    discardAudio.current = true;
    setTurns((ts) => [
      ...ts.map((t) => (t.id === prev && !t.agent.done ? { ...t, agent: { ...t.agent, done: true, interrupted: true } } : t)),
      { id, caller, agent: { text: "", tools: [], done: false } },
    ]);
    return id;
  }, []);

  const send = useCallback((m: VoiceClientMessage) => {
    if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(JSON.stringify(m));
  }, []);

  // ── Playback ──
  const stopPlayback = useCallback(() => {
    try { window.speechSynthesis?.cancel(); } catch { /* ignore */ }
    const p = player.current;
    player.current = undefined;
    p?.stop();
    setActivity((a) => (a === "speaking" ? "idle" : a));
  }, []);

  const markPerceived = useCallback((id: number | undefined) => {
    const t0 = releasedAt.current;
    if (t0 == null) return;
    releasedAt.current = undefined;
    patchTurn(id, (t) => ({ ...t, perceivedMs: Math.round(performance.now() - t0) }));
  }, [patchTurn]);

  const speak = useCallback((text: string, id: number | undefined) => {
    const synth = window.speechSynthesis;
    if (!synth || !text.trim()) { setActivity("idle"); return; }
    stopPlayback();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "fr-FR";
    const fr = synth.getVoices().find((v) => v.lang?.toLowerCase().startsWith("fr"));
    if (fr) u.voice = fr;
    u.rate = 1.08;
    u.onstart = () => { setActivity("speaking"); markPerceived(id); };
    u.onend = u.onerror = () => setActivity((a) => (a === "speaking" ? "idle" : a));
    setActivity("speaking");
    synth.speak(u);
  }, [markPerceived, stopPlayback]);

  // ── Server messages ──
  const onMessage = useCallback((ev: MessageEvent) => {
    if (typeof ev.data !== "string") {
      if (!discardAudio.current) player.current?.push(ev.data as ArrayBuffer);
      return;
    }
    let m: VoiceServerMessage;
    try { m = JSON.parse(ev.data); } catch { return; }
    const id = currentTurn.current;
    switch (m.type) {
      case "ready":
        sessionId.current = m.sessionId;
        setProviders({ llm: m.llm, stt: m.stt, tts: m.tts, sessionId: m.sessionId });
        setConn("ready");
        break;
      case "transcript": {
        const turn = id;
        if (!m.final) {
          // Live partial while the caller speaks (or just after the release): never over a final text.
          patchTurn(turn, (t) => (t.caller.status === "final" ? t : { ...t, caller: { ...t.caller, text: m.text, stable: m.stable ?? "" } }));
          break;
        }
        // Typed turns already show the caller text; the server echoes it as a transcript.
        if (turn == null) newTurn({ text: m.text, at: Date.now(), status: "final" });
        else patchTurn(turn, (t) => ({ ...t, caller: { ...t.caller, text: m.text, status: "final" } }));
        setActivity((a) => (a === "recording" ? a : "thinking"));
        break;
      }
      case "agent_text":
        patchTurn(id, (t) => ({ ...t, agent: { ...t.agent, text: t.agent.text + m.delta, at: t.agent.at ?? Date.now() } }));
        break;
      case "agent_tool":
        patchTurn(id, (t) => {
          const tools = [...t.agent.tools];
          if (m.ok === undefined) tools.push({ id: `${t.id}-${tools.length}`, name: m.name, args: m.args });
          else {
            const i = tools.findIndex((x) => x.name === m.name && x.ok === undefined);
            if (i >= 0) tools[i] = { ...tools[i], ok: m.ok, ms: m.ms };
            else tools.push({ id: `${t.id}-${tools.length}`, name: m.name, ok: m.ok, ms: m.ms });
          }
          return { ...t, agent: { ...t.agent, tools, at: t.agent.at ?? Date.now() } };
        });
        break;
      case "agent_audio_start":
        discardAudio.current = false;
        audioMime.current = m.mime;
        turnHasAudio.current = true;
        if (m.mime !== MOCK_TTS_MIME) {
          stopPlayback();
          const p: SegmentPlayer = new SegmentPlayer(m.mime, {
            onPlaying: () => { setActivity("speaking"); markPerceived(id); },
            onEnded: () => {
              if (player.current === p) player.current = undefined;
              setActivity((a) => (a === "speaking" ? "idle" : a));
            },
          });
          player.current = p;
        }
        break;
      case "agent_audio_end":
        // An interrupted turn's segment closes after the new turn started: drop it.
        if (discardAudio.current) break;
        player.current?.end();
        break;
      case "agent_done":
        patchTurn(id, (t) => ({ ...t, timings: m.timings, agent: { ...t.agent, done: true, text: t.agent.text || m.text } }));
        if (audioMime.current === MOCK_TTS_MIME && turnHasAudio.current) speak(m.text, id);
        else if (!turnHasAudio.current || !player.current) setActivity((a) => (a === "thinking" ? "idle" : a));
        audioMime.current = undefined;
        currentTurn.current = undefined;
        break;
      case "error":
        setLastError(m.message);
        if (id != null) patchTurn(id, (t) => ({ ...t, caller: { ...t.caller, status: "final" }, agent: { ...t.agent, done: true, error: m.message } }));
        currentTurn.current = undefined;
        setActivity((a) => (a === "thinking" ? "idle" : a));
        break;
    }
  }, [markPerceived, newTurn, patchTurn, speak, stopPlayback]);

  // ── Connection (auto-reconnect, same sessionId keeps the server-side history) ──
  const connect = useCallback(() => {
    if (!alive.current) return;
    ws.current?.close();
    setConn("connecting");
    const sock = new WebSocket(wsUrl());
    sock.binaryType = "arraybuffer";
    ws.current = sock;
    sock.onopen = () => sock.send(JSON.stringify({ type: "start", sessionId: sessionId.current, actorName: "Agent vocal" } satisfies VoiceClientMessage));
    sock.onmessage = onMessage;
    sock.onclose = () => {
      if (ws.current !== sock) return;
      setConn("offline");
      setActivity((a) => (a === "speaking" ? a : "idle"));
      if (alive.current) window.setTimeout(() => { if (ws.current === sock) connect(); }, 3000);
    };
  }, [onMessage]);

  useEffect(() => {
    alive.current = true;
    connect();
    return () => {
      alive.current = false;
      const s = ws.current;
      ws.current = undefined;
      s?.close();
      stopPlayback();
      if (raf.current) cancelAnimationFrame(raf.current);
      try { recorder.current?.stop(); } catch { /* ignore */ }
      stream.current?.getTracks().forEach((t) => t.stop());
      void audioCtx.current?.close().catch(() => undefined);
    };
  }, [connect, stopPlayback]);

  // ── Mic ──
  const ensureMic = useCallback(async (): Promise<MediaStream | undefined> => {
    if (stream.current?.active) return stream.current;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") { setMic("unsupported"); return undefined; }
    try {
      const s = await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true } });
      stream.current = s;
      setMic("granted");
      const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      const ctx = new Ctx();
      const an = ctx.createAnalyser();
      an.fftSize = 512;
      ctx.createMediaStreamSource(s).connect(an);
      audioCtx.current = ctx;
      analyser.current = an;
      return s;
    } catch (e) {
      setMic((e as DOMException).name === "NotAllowedError" || (e as DOMException).name === "SecurityError" ? "denied" : "unsupported");
      return undefined;
    }
  }, []);

  const meter = useCallback(() => {
    const an = analyser.current;
    if (!an) return;
    const buf = new Uint8Array(an.fftSize);
    const tick = () => {
      an.getByteTimeDomainData(buf);
      let sum = 0;
      for (const v of buf) { const x = (v - 128) / 128; sum += x * x; }
      setLevel(Math.min(1, Math.sqrt(sum / buf.length) * 4));
      raf.current = requestAnimationFrame(tick);
    };
    tick();
  }, []);

  const startTalking = useCallback(async () => {
    if (pressed.current || conn !== "ready") return;
    pressed.current = true;
    stopPlayback();
    const s = await ensureMic();
    // Released while the permission prompt / mic warm-up was pending: do not record a stub.
    if (!s || !pressed.current) { pressed.current = false; return; }
    const mime = REC_MIME.find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
    const rec = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
    recorder.current = rec;
    send({ type: "audio_start", mime: rec.mimeType || mime || "audio/webm" });
    rec.ondataavailable = (e) => { if (e.data.size && ws.current?.readyState === WebSocket.OPEN) ws.current.send(e.data); };
    rec.onstop = () => {
      // The last dataavailable fires before stop, so every chunk has been queued on the socket.
      send({ type: "audio_end" });
      releasedAt.current = performance.now();
    };
    void audioCtx.current?.resume();
    rec.start(100); // a chunk every 100 ms: the STT hears the words while they are spoken
    newTurn({ text: "", at: Date.now(), status: "recording" });
    setActivity("recording");
    setLastError(undefined);
    meter();
  }, [conn, ensureMic, meter, newTurn, send, stopPlayback]);

  const stopTalking = useCallback(() => {
    if (!pressed.current) return;
    pressed.current = false;
    if (raf.current) cancelAnimationFrame(raf.current);
    setLevel(0);
    const rec = recorder.current;
    recorder.current = undefined;
    if (rec && rec.state !== "inactive") {
      rec.stop();
      patchTurn(currentTurn.current, (t) => ({ ...t, caller: { ...t.caller, status: "transcribing" } }));
      setActivity("thinking");
    }
  }, [patchTurn]);

  const sendText = useCallback((text: string) => {
    const v = text.trim();
    if (!v || conn !== "ready") return;
    stopPlayback();
    newTurn({ text: v, at: Date.now(), status: "final", typed: true });
    send({ type: "text", text: v });
    releasedAt.current = performance.now();
    setActivity("thinking");
    setLastError(undefined);
  }, [conn, newTurn, send, stopPlayback]);

  const reset = useCallback(() => {
    stopPlayback();
    send({ type: "reset" });
    currentTurn.current = undefined;
    setTurns([]);
    setActivity("idle");
    setLastError(undefined);
  }, [send, stopPlayback]);

  return {
    conn, activity, mic, providers, turns, level, lastError,
    startTalking, stopTalking, sendText, stopPlayback, reset, reconnect: connect,
  };
}
