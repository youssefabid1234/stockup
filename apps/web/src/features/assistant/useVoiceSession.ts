/**
 * Push-to-talk voice session over WS /ai/voice (contract: VoiceClientMessage / VoiceServerMessage in @kit/shared).
 * Mic → MediaRecorder (webm/opus) chunks every 100 ms, streamed as binary frames between audio_start and audio_end:
 * the server transcribes them as they arrive and sends `transcript` final:false (live text) before the final one.
 * Agent audio: binary frames between agent_audio_start/end → one Blob → <audio>. Mock TTS → speechSynthesis (fr-FR).
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { MOCK_TTS_MIME, type CallerReady, type TurnTimings, type VoiceClientMessage, type VoiceServerMessage } from "@kit/shared";

/** Team 12: what the caller ID form sends (an ERP client, or a new client). */
export type CallerInput = Omit<Extract<VoiceClientMessage, { type: "caller" }>, "type">;
import { AI_BASE } from "@/lib/api";
import { SegmentPlayer } from "./audio-player";
import type { ToolRun } from "./tools";

export type Conn = "connecting" | "ready" | "offline";
export type Activity = "idle" | "recording" | "thinking" | "speaking";
export type MicState = "unknown" | "granted" | "denied" | "unsupported";

export interface VoiceTurn {
  id: number;
  /** text: live while recording/transcribing (stable = its final words), definitive once status is "final". */
  caller: { text: string; stable?: string; at: number; status: "recording" | "transcribing" | "final"; typed?: boolean; silent?: boolean };
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
  const [answering, setAnswering] = useState(false); // team 12: the answer itself is being spoken (not the fillers)
  const [mic, setMic] = useState<MicState>("unknown");
  const [providers, setProviders] = useState<Providers>();
  const [turns, setTurns] = useState<VoiceTurn[]>([]);
  const [level, setLevel] = useState(0);
  const [lastError, setLastError] = useState<string>();
  // Team 12: the caller, identified before the call (caller ID form). No talking until it is set.
  const [caller, setCaller] = useState<CallerReady>();
  const [callerPending, setCallerPending] = useState(false);
  // What the form sent: re-sent (resume) after every reconnect, so the agent never forgets the caller even if the
  // AI service restarted (its conversations live in memory).
  const callerInput = useRef<CallerInput>();

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
  const levelBuf = useRef<Uint8Array<ArrayBuffer>>(); // team 12 (Youssef): hands-free reads the mic level (readRms)
  const tentative = useRef<{ chunks: Blob[]; mime: string } | null>(null); // team 12: a sound being checked (soft barge-in)
  const quietEmpty = useRef(false); // team 12: a hands-free noise heard as nothing: drop the turn, no error shown
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
      // team 12 (Youssef): a caller piece cut before its final transcript (hands-free) never stays « Transcription… »:
      // its words are kept (the server merges them into the next message) or, if nothing was heard, it disappears
      ...ts
        .filter((t) => !(t.id === prev && t.caller.status !== "final" && !t.caller.text.trim() && !t.agent.text))
        .map((t) => (t.id === prev && t.caller.status !== "final" ? { ...t, caller: { ...t.caller, status: "final" as const } } : t))
        .map((t) => (t.id === prev && !t.agent.done ? { ...t, agent: { ...t.agent, done: true, interrupted: true } } : t)),
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
    setAnswering(false);
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
        // Reconnected during a call: tell the server again who is calling (keeps the conversation).
        if (callerInput.current && ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send(JSON.stringify({ type: "caller", ...callerInput.current, resume: true } satisfies VoiceClientMessage));
        }
        break;
      case "caller_ready":
        setCaller(m);
        setCallerPending(false);
        if (!m.resume) setTurns([]);
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
      case "nudge_said": {
        // team 12 (Youssef): hands-free, the caller was silent: the agent's short line (its audio follows)
        releasedAt.current = undefined; // no « perceived latency » chip on a nudge (nobody released a key)
        const nid = newTurn({ text: "", at: Date.now(), status: "final", silent: true });
        patchTurn(nid, (t) => ({ ...t, agent: { ...t.agent, text: m.text, at: Date.now(), done: true } }));
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
              setAnswering(false);
              setActivity((a) => (a === "speaking" ? "idle" : a));
            },
          });
          player.current = p;
        }
        break;
      case "agent_answer_start":
        if (!discardAudio.current) setAnswering(true);
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
        if (m.code === "outbound_unavailable") {
          callerInput.current = undefined;
          setCaller(undefined);
          setCallerPending(false);
        }
        if (quietEmpty.current && m.message.startsWith("Rien entendu")) {
          // team 12: hands-free picked up a noise, not a sentence: forget it silently
          quietEmpty.current = false;
          if (id != null) setTurns((ts) => ts.filter((t) => t.id !== id));
          currentTurn.current = undefined;
          setActivity((a) => (a === "thinking" ? "idle" : a));
          break;
        }
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

  const startTalking = useCallback(async (opts?: { tentative?: boolean }) => {
    if (pressed.current || conn !== "ready" || !caller) return;
    pressed.current = true;
    if (opts?.tentative && player.current) {
      // team 12 (Youssef): a sound while Lucie speaks: record it locally, lower her voice, decide in a moment
      const s = await ensureMic();
      if (!s || !pressed.current) { pressed.current = false; return; }
      const mime = REC_MIME.find((t) => MediaRecorder.isTypeSupported(t)) ?? "";
      const rec = new MediaRecorder(s, mime ? { mimeType: mime } : undefined);
      recorder.current = rec;
      tentative.current = { chunks: [], mime: rec.mimeType || mime || "audio/webm" };
      rec.ondataavailable = (e) => {
        if (!e.data.size) return;
        if (tentative.current) tentative.current.chunks.push(e.data);
        else if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(e.data);
      };
      rec.onstop = () => { if (!tentative.current) send({ type: "audio_end" }); };
      rec.start(100);
      player.current?.setVolume(0.2);
      return;
    }
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
    };
    void audioCtx.current?.resume();
    rec.start(100); // a chunk every 100 ms: the STT hears the words while they are spoken
    newTurn({ text: "", at: Date.now(), status: "recording" });
    setActivity("recording");
    setLastError(undefined);
    meter();
  }, [caller, conn, ensureMic, meter, newTurn, send, stopPlayback]);

  /** Team 12 (Youssef): the sound being checked is real speech: Lucie stops, the caller is heard from the first syllable. */
  const confirmTalking = useCallback(() => {
    const t = tentative.current;
    if (!t || !pressed.current) return;
    tentative.current = null;
    stopPlayback();
    send({ type: "audio_start", mime: t.mime });
    for (const c of t.chunks) if (ws.current?.readyState === WebSocket.OPEN) ws.current.send(c);
    void audioCtx.current?.resume();
    newTurn({ text: "", at: Date.now(), status: "recording" });
    setActivity("recording");
    setLastError(undefined);
    meter();
  }, [meter, newTurn, send, stopPlayback]);

  /** Team 12 (Youssef): it was only a noise: forget it, Lucie's voice comes back up, as if nothing happened. */
  const cancelTalking = useCallback(() => {
    if (!tentative.current) return;
    tentative.current = null;
    pressed.current = false;
    const rec = recorder.current;
    recorder.current = undefined;
    if (rec && rec.state !== "inactive") { rec.onstop = null; rec.stop(); }
    player.current?.setVolume(1);
  }, []);

  /** `quiet`: hands-free ended it (an empty transcript is then a noise, dropped without an error). */
  const stopTalking = useCallback((opts?: { quiet?: boolean }) => {
    if (!pressed.current) return;
    pressed.current = false;
    quietEmpty.current = !!opts?.quiet;
    if (raf.current) cancelAnimationFrame(raf.current);
    setLevel(0);
    const rec = recorder.current;
    recorder.current = undefined;
    if (rec && rec.state !== "inactive") {
      releasedAt.current = performance.now();
      rec.stop();
      patchTurn(currentTurn.current, (t) => ({ ...t, caller: { ...t.caller, status: "transcribing" } }));
      setActivity("thinking");
    }
  }, [patchTurn]);

  const sendText = useCallback((text: string) => {
    const v = text.trim();
    if (!v || conn !== "ready" || !caller) return;
    stopPlayback();
    newTurn({ text: v, at: Date.now(), status: "final", typed: true });
    releasedAt.current = performance.now();
    send({ type: "text", text: v });
    setActivity("thinking");
    setLastError(undefined);
  }, [caller, conn, newTurn, send, stopPlayback]);

  /** Team 12: announce the caller (the server loads their sheet, then answers caller_ready). */
  const identifyCaller = useCallback((input: CallerInput) => {
    if (conn !== "ready") return;
    stopPlayback();
    setCallerPending(true);
    setLastError(undefined);
    callerInput.current = input;
    send({ type: "caller", ...input });
  }, [conn, send, stopPlayback]);

  /** Team 12: hang up: back to the caller ID form, fresh conversation. */
  const endCall = useCallback(() => {
    // team 12 (Youssef): hanging up stops everything that costs: a recording in progress is dropped (no audio
    // reaches the STT any more), the mic is released (hands-free stops listening), the server cancels the running
    // turn (LLM + TTS) on "reset", and the agent's audio stops.
    pressed.current = false;
    const rec = recorder.current;
    recorder.current = undefined;
    if (rec && rec.state !== "inactive") {
      rec.ondataavailable = null;
      rec.onstop = null;
      try { rec.stop(); } catch { /* already stopped */ }
    }
    if (raf.current) cancelAnimationFrame(raf.current);
    setLevel(0);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = undefined;
    analyser.current = undefined;
    void audioCtx.current?.close().catch(() => undefined);
    audioCtx.current = undefined;
    stopPlayback();
    send({ type: "reset", hangUp: true });
    currentTurn.current = undefined;
    setTurns([]);
    setCaller(undefined);
    callerInput.current = undefined;
    setActivity("idle");
  }, [send, stopPlayback]);

  const reset = useCallback(() => {
    stopPlayback();
    send({ type: "reset" });
    currentTurn.current = undefined;
    setTurns([]);
    setActivity("idle");
    setLastError(undefined);
  }, [send, stopPlayback]);

  /** Team 12 (Youssef): current mic loudness (RMS 0..1), for hands-free speech detection. undefined = no mic yet. */
  const readRms = useCallback((): number | undefined => {
    const an = analyser.current;
    if (!an) return undefined;
    const buf = (levelBuf.current ??= new Uint8Array(an.fftSize));
    an.getByteTimeDomainData(buf);
    let sum = 0;
    for (const v of buf) { const x = (v - 128) / 128; sum += x * x; }
    return Math.sqrt(sum / buf.length);
  }, []);

  return {
    conn, activity, answering, mic, providers, turns, level, lastError,
    startTalking, stopTalking, confirmTalking, cancelTalking, sendText, stopPlayback, reset, reconnect: connect,
    ensureMic, readRms,
    nudge: () => send({ type: "nudge" }), // team 12 (Youssef): hands-free silence → one short line from the agent
    caller, callerPending, identifyCaller, endCall,
  };
}
