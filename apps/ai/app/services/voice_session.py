"""
WS /voice — push-to-talk voice sessions (messages: app/schemas/voice.py).

One turn:
    audio_start … binary frames … audio_end   (or a typed `text` message)
      → STT, live: each frame goes to the provider as it arrives (services/utterance.py);
        "transcript" final:false while the caller speaks, then "transcript" final:true soon after audio_end
      → agent (voice mode) streaming "agent_tool", then "agent_text" with the completed reply
      → each finished sentence goes to TTS right away (sentence by sentence = first audio sooner)
      → "agent_audio_start" {mime}, binary audio chunks…, "agent_audio_end"   (one audio segment per turn)
      → "agent_done" {text, timings}

Barge-in: a new audio_start / text while the agent is still busy cancels the running turn (asyncio
cancellation); what was heard and said so far stays in the history.
"""

import asyncio
import json
import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from contextlib import aclosing, suppress
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from app import team_flags
from app.agent import call_context as preload
from app.agent import listening
from app.agent import run_agent, sanitize_history
from app.agent.call_context import CallContext
from app.agent.loop import ms_since
from app.agent.orchestrator import Anticipation, get_fast_llm_client, run_voice_turn
from app.agent.router import pick_llm
from app.clients import STTUpdate, TTSClient, get_llm_client, get_stt_client, get_tts_client
from app.config import settings
from app.schemas import (
    AgentAudioEndMessage,
    AgentAudioStartMessage,
    AgentDoneMessage,
    AgentTextMessage,
    AgentToolMessage,
    AudioEndMessage,
    AudioStartMessage,
    CallerMessage,
    CallerReadyMessage,
    NudgeMessage,
    NudgeSaidMessage,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    ReadyMessage,
    ResetMessage,
    StartMessage,
    TextEvent,
    TextMessage,
    ToolCallEvent,
    ToolResultEvent,
    TranscriptMessage,
    TurnTimings,
    VoiceClientMessage,
    VoiceErrorMessage,
)
from app.schemas.base import WireModel
from app.tools import ErpClient, all_tools

from . import fillers
from .utterance import Utterance
from .vocabulary import stt_hint
from .voice_reply import one_question, spoken_reply, vary_closing, vary_opening, without_repeated_greeting

client_message = TypeAdapter(VoiceClientMessage)

CALL_GREETINGS = {None: "Bonjour.", "madame": "Bonjour Madame.", "monsieur": "Bonjour Monsieur."}
GREETING_PREPARE_TIMEOUT = 3.0  # mode 4 greeting is a full sentence; plays as soon as ready


@dataclass
class Conversation:
    id: str
    actor_name: str | None = None
    history: list[ChatMessage] = field(default_factory=list)
    call_context: CallContext | None = None  # team 12 (Youssef): the caller's sheet, once known (TEAM_PRELOAD)
    opening_greeting: str | None = None
    agent_opened: bool = False  # mode 4: the agent already said « Bonjour…, que puis-je faire pour vous ? »
    # team 12 (Youssef): what the caller said that the agent has not answered yet (pieces, oldest first): merged
    # into one message so a new piece never makes the agent forget the previous ones (agent/listening.py)
    pending: list[str] = field(default_factory=list)
    last_spoken: str | None = None  # team 12 (Youssef): the previous reply, so the next one opens differently
    used_closings: list[str] = field(default_factory=list)  # team 12: validation questions already asked


# In memory: a reconnect with the same sessionId continues the conversation.
conversations: dict[str, Conversation] = {}


class VoiceConnection:
    """One WebSocket connection. Reads client messages; runs each turn as a background task."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.conversation: Conversation | None = None
        self.recording: Utterance | None = None  # while the key is down
        self.turn: asyncio.Task | None = None
        self.anticipation: Anticipation | None = None  # team 12 (TEAM_ORCHESTRATOR): ERP checked while the caller speaks
        self.warm_up: asyncio.Task | None = None
        self.bank = fillers.FillerBank()
        self.greetings: dict[str, fillers.CachedAudio] = {}
        self.audio_warm_up: asyncio.Task | None = None
        self._send_lock = asyncio.Lock()

    # ── sending ──

    async def send(self, msg: WireModel) -> None:
        await self._send(text=msg.to_json())

    async def send_bytes(self, data: bytes) -> None:
        await self._send(bytes=data)

    async def _send(self, **message) -> None:
        async with self._send_lock:
            with suppress(WebSocketDisconnect, RuntimeError):  # the client is gone: nothing to do
                if message.get("text") is not None:
                    await self.ws.send_text(message["text"])
                else:
                    await self.ws.send_bytes(message["bytes"])

    # ── receiving ──

    async def serve(self) -> None:
        await self.ws.accept()
        try:
            while True:
                frame = await self.ws.receive()
                if frame["type"] == "websocket.disconnect":
                    break
                if frame.get("bytes") is not None:
                    if self.recording:
                        self.recording.feed(frame["bytes"])
                    continue
                await self.handle_text(frame.get("text") or "")
        except WebSocketDisconnect:
            pass
        finally:
            await self.interrupt()
            if self.audio_warm_up:
                self.audio_warm_up.cancel()
                with suppress(asyncio.CancelledError):
                    await self.audio_warm_up

    async def handle_text(self, raw: str) -> None:
        try:
            msg = client_message.validate_python(json.loads(raw))
        except (json.JSONDecodeError, ValidationError):
            await self.send(VoiceErrorMessage(message="invalid JSON message"))
            return
        if not self.conversation and not isinstance(msg, StartMessage):
            await self.open()  # no "start" yet: open a fresh conversation

        match msg:
            case StartMessage(session_id=session_id, actor_name=actor_name):
                await self.interrupt()
                await self.open(session_id, actor_name)
            case AudioStartMessage(mime=mime, hint=hint):
                await self.interrupt()  # barge-in
                self.recording = Utterance(get_stt_client(), mime, hint, on_partial=self.send_partial)
                if team_flags.orchestrator():
                    self.anticipation = Anticipation(self.conversation.call_context, self.conversation.actor_name)
            case AudioEndMessage():
                if self.recording:
                    utterance, self.recording = self.recording, None
                    anticipated, self.anticipation = self.anticipation, None
                    self.start_turn(utterance=utterance, anticipated=anticipated)
            case TextMessage(text=text):
                await self.interrupt()
                self.start_turn(text=text)
            case ResetMessage():
                await self.interrupt()
                self.conversation.history = []
                self.conversation.pending = []
                self.conversation.used_closings = []
                self.conversation.opening_greeting = None
                await self.open(self.conversation.id)
            case CallerMessage():  # team 12 (Youssef): caller ID form, before the call
                await self.interrupt()
                await self.set_caller(msg)
            case NudgeMessage():  # team 12 (Youssef): hands-free, the caller has been silent for a while
                await self.nudge()

    async def nudge(self) -> None:
        """One short, varied line after a silence (« Vous êtes toujours là ? »): no model, no history, never while
        the caller speaks or the agent works. The page sends it once per silence (hands-free only)."""
        if self.recording or (self.turn and not self.turn.done()):
            return
        self.nudges = getattr(self, "nudges", None) or fillers.PhraseRotation(fillers.NUDGES)
        line = self.nudges.next()
        await self.send(NudgeSaidMessage(text=line))
        speaker = Speaker(get_tts_client(), self.send, self.send_bytes, self.bank)
        speaker.push(line)
        await speaker.finish()

    async def send_partial(self, update: STTUpdate) -> None:
        if self.anticipation:  # team 12: the colleague starts on the words heard so far (never blocks)
            self.anticipation.heard(update.text)
        await self.send(TranscriptMessage(text=update.text, final=False, stable=update.stable))

    async def set_caller(self, msg: CallerMessage) -> None:
        """Team 12 (Youssef): who is calling, from the caller ID form. Their sheet is loaded now and ALWAYS given to the
        agent (the caller was chosen explicitly). A new call starts a fresh history; `resume` (sent again by the page
        after a reconnect, e.g. the AI service reloaded) only restores the caller and keeps the conversation."""
        conv = self.conversation
        opening_enabled = team_flags.fillers()
        if not msg.resume:
            conv.history = []
            conv.pending = []  # team 12 (Youssef): a new call starts with nothing pending
            conv.used_closings = []
            conv.agent_opened = False
            greetings = fillers.OPENING_LINES if team_flags.no_silence() else CALL_GREETINGS  # mode 4: the agent opens
            conv.opening_greeting = greetings[msg.contact_title] if opening_enabled else None
        async with asyncio.TaskGroup() as preparation:
            if team_flags.no_silence() and not msg.resume and conv.opening_greeting:
                # mode 4: say « Bonjour…, que puis-je faire pour vous ? » as soon as the clip is ready, while the
                # caller's sheet is still loading (it does not need the sheet)
                preparation.create_task(self.prepare_and_open(conv, conv.opening_greeting))
            elif opening_enabled and (greeting := conv.opening_greeting) and greeting not in self.greetings:
                preparation.create_task(self.prepare_greeting(greeting))
            try:
                sheet = await preload.caller_context(
                    ErpClient("voice_agent"),
                    client_id=msg.client_id,
                    phone=msg.phone,
                    contact_name=msg.contact_name,
                    company_name=msg.company_name,
                    is_new=msg.is_new,
                )
            except Exception as e:  # ERP down…: the call still works, the agent will look the client up itself
                await self.send(VoiceErrorMessage(message=f"Fiche client indisponible : {e}"))
                sheet = None
        used = sheet is not None
        conv.call_context = sheet
        await self.send(
            CallerReadyMessage(
                client_id=sheet.client_id or None if sheet else None,
                name=sheet.name if sheet else (msg.company_name or "Appelant inconnu"),
                contact_name=(sheet.caller_contact if sheet else None) or msg.contact_name,
                is_new=bool(sheet and sheet.is_new),
                status=sheet.status if sheet else None,
                loaded_ms=sheet.loaded_ms if sheet else None,
                used_by_agent=used,
                resume=msg.resume,
            )
        )

    async def prepare_and_open(self, conv: Conversation, greeting: str) -> None:
        if greeting not in self.greetings:
            await self.prepare_greeting(greeting)
        await self.open_the_call(conv)

    async def open_the_call(self, conv: Conversation) -> None:
        """Mode 4: like a real switchboard, the agent speaks first as soon as the call starts (« Bonjour Madame, que
        puis-je faire pour vous ? »). The clip was synthesized while the caller's sheet was loading; its own audio
        segment. The first reply then skips its own « Bonjour »."""
        clip = self.greetings.get(conv.opening_greeting or "")
        if clip is None:
            return  # not ready (TTS slow): the classic greeting plays on the first release instead
        speaker = Speaker(get_tts_client(), self.send, self.send_bytes, self.bank)
        await speaker.play_audio(clip.mime, clip.data)
        await self.send(AgentAudioEndMessage())
        conv.opening_greeting = None
        conv.agent_opened = True

    async def open(self, session_id: str | None = None, actor_name: str | None = None) -> None:
        conv = conversations.get(session_id or "") or Conversation(id=session_id or str(uuid.uuid4()))
        if actor_name:
            conv.actor_name = actor_name
        conversations[conv.id] = self.conversation = conv
        llm = get_llm_client()
        await self.send(
            ReadyMessage(session_id=conv.id, stt=get_stt_client().name, tts=get_tts_client().name, llm=f"{llm.provider}:{llm.model}")
        )
        # Fetch the company vocabulary for the STT now, not when the caller first speaks.
        self.warm_up = self.warm_up or asyncio.create_task(stt_hint(get_stt_client().name, None))

        if team_flags.fillers() and self.audio_warm_up is None:
            self.audio_warm_up = asyncio.create_task(self.prepare_audio())

    async def prepare_audio(self) -> None:
        try:
            await self.bank.warm_up(get_tts_client(), settings.tts.voice or None)
        except Exception as exc:
            # An optional clip must never prevent the customer from placing an order.
            logging.getLogger(__name__).warning("Waiting audio unavailable (%s)", type(exc).__name__)
            self.audio_warm_up = None

    async def prepare_greeting(self, greeting: str) -> None:
        try:
            tts = get_tts_client()
            if tts.name == "mock":
                return
            async with asyncio.timeout(GREETING_PREPARE_TIMEOUT):
                clip = await fillers.synthesize_clip(tts, greeting, settings.tts.voice or None)
            if clip.mime == "audio/mpeg":
                self.greetings[greeting] = clip
        except Exception as exc:
            logging.getLogger(__name__).debug("Opening greeting unavailable (%s)", type(exc).__name__)

    def start_turn(self, **turn_input) -> None:
        self.turn = asyncio.create_task(self.run_turn(self.conversation, **turn_input))

    async def interrupt(self) -> None:
        """Barge-in: drop a recording in progress, stop the running turn and wait until it has cleaned up."""
        if self.recording:
            self.recording.cancel()
            self.recording = None
        if self.anticipation:
            self.anticipation.cancel()
            self.anticipation = None
        if self.turn and not self.turn.done():
            self.turn.cancel()
            with suppress(asyncio.CancelledError):
                await self.turn
        self.turn = None

    # ── one turn ──

    async def run_turn(
        self,
        conv: Conversation,
        text: str | None = None,
        utterance: Utterance | None = None,  # spoken: already being transcribed since audio_start
        anticipated: Anticipation | None = None,  # team 12: ERP facts fetched while the caller was speaking
    ) -> None:
        t0 = time.perf_counter()  # end of caller speech
        timings = TurnTimings()
        heard, spoken = "", ""
        history_size = len(conv.history)
        working: list[ChatMessage] | None = None
        committed = False
        speaker: Speaker | None = None
        greeted = conv.agent_opened  # mode 4: the agent opened the call, its first reply must not say « Bonjour » again
        conv.agent_opened = False
        try:
            # The caller form prepared this clip. Play it before waiting for the final transcript.
            if conv.opening_greeting and team_flags.fillers():
                clip = self.greetings.get(conv.opening_greeting)
                if clip and (utterance.frames if utterance is not None else (text or "").strip()):
                    speaker = Speaker(get_tts_client(), self.send, self.send_bytes, self.bank)
                    await speaker.play_audio(clip.mime, clip.data)
                    greeted = True
                    conv.opening_greeting = None

            # 1. Speech → text: with a streaming STT only the last words are left to finalize
            early = None
            if utterance is not None and team_flags.no_silence():  # team 12: « je regarde » before the final transcript
                speaker = speaker or Speaker(get_tts_client(), self.send, self.send_bytes, self.bank)
                early = asyncio.create_task(fillers.early_acknowledgement(speaker, utterance))
            if utterance is not None:
                try:
                    text = await utterance.text()
                except asyncio.CancelledError:
                    # team 12 (Youssef): the caller spoke again before this piece was final: keep what was heard
                    if partial := (getattr(utterance, "partial", "") or "").strip():
                        conv.pending.append(partial)
                    if early is not None:
                        early.cancel()
                    raise
                finally:
                    if early is not None:
                        speaker.transcript_ready = True
                        if not early.done():
                            await asyncio.wait({early}, timeout=1.0)
                timings.stt_ms = ms_since(t0)  # end of speech → final transcript
            heard = (text or "").strip()
            if not heard:
                if speaker:
                    await speaker.stop()
                await self.send(VoiceErrorMessage(message="Rien entendu — réessayez."))
                return
            conv.opening_greeting = None
            await self.send(TranscriptMessage(text=heard, final=True))

            # 2. Agent, on a working copy of the history (committed at the end)
            # team 12 (Youssef): every piece not answered yet + this one, as ONE message (marks: listening.py)
            conv.pending = [*conv.pending, getattr(utterance, "annotated", None) or heard]
            working = [*conv.history, ChatMessage(role="user", content=listening.merge_parts(conv.pending))]
            speaker = speaker or Speaker(get_tts_client(), self.send, self.send_bytes, self.bank)
            await fillers.on_turn_start(speaker, heard)  # team 12 (Mohamed Amine): no-op while TEAM_FILLERS is off
            llm_start = time.perf_counter()
            # team 12 (Youssef): the orchestrator when TEAM_ORCHESTRATOR is on, else the kit's agent loop
            agent = run_voice_turn if team_flags.orchestrator() else run_agent
            extra = {"call_context": conv.call_context} if conv.call_context is not None else {}
            if anticipated is not None and agent is run_voice_turn:
                extra["anticipated"] = anticipated
            # TEAM_ROUTER: « c'est bon, validez », « merci » → the fast model (2-3× faster); the rest → the main model
            # team 12 (Youssef): several pieces pending → route on the whole request, not just the last « merci »
            route_on = heard if len(conv.pending) == 1 else listening.merge_parts(conv.pending)
            llm, model_used = pick_llm(route_on, get_llm_client(), get_fast_llm_client)
            if model_used == "rapide":
                print(f"[router] modèle rapide pour « {heard} »", flush=True)
            async for ev in agent(working, llm=llm, tools=all_tools(), mode="voice", actor_name=conv.actor_name, **extra):
                match ev:
                    case TextEvent(delta=delta) if delta.strip():
                        if timings.llm_first_token_ms is None:
                            timings.llm_first_token_ms = ms_since(llm_start)
                    case ToolCallEvent(call=call):
                        await self.send(AgentToolMessage(name=call.name, args=call.arguments))
                        await fillers.on_tool_call(speaker, call.name)  # team 12 (Mohamed Amine)
                    case ToolResultEvent(name=name, ok=ok, ms=ms):
                        await self.send(AgentToolMessage(name=name, ok=ok, ms=ms))
                    case DoneEvent(message=message):
                        spoken = spoken_reply(message.content) or "Je n’ai pas de réponse à vous donner pour le moment."
                        if greeted:
                            contact = conv.call_context.caller_contact if conv.call_context else None
                            spoken = without_repeated_greeting(spoken, contact)
                        spoken = vary_opening(spoken, conv.last_spoken)  # team 12 (Youssef): no « Parfait, » twice in a row
                        spoken = vary_closing(one_question(spoken), conv.used_closings)  # one question, varied closing
                    case ErrorEvent(message=message):
                        await speaker.stop_waiting()
                        await self.send(VoiceErrorMessage(message=message))
            timings.llm_total_ms = ms_since(llm_start)
            conv.history = trim_voice_turn(working, history_size, spoken)
            committed = True
            conv.pending = []  # team 12: answered
            conv.last_spoken = spoken or conv.last_spoken

            # Only the completed reply goes to the caller. Text emitted before a tool call may be internal notes.
            if spoken:
                if not team_flags.no_silence():  # mode 4 types on until the answer's first audio byte
                    await speaker.stop_waiting()
                await self.send(AgentTextMessage(delta=spoken))
                speaker.push(spoken)
            await speaker.finish()
            timings.tts_first_byte_ms = speaker.tts_first_byte_ms
            if speaker.first_byte_at:
                timings.total_ms = int((speaker.first_byte_at - t0) * 1000 + 0.5)
            print(f"[tour] transcription {timings.stt_ms} ms · modèle {timings.llm_total_ms} ms · 1er son {timings.total_ms} ms"
                  f" · « {heard[:60]} »", flush=True)  # team 12: per-turn timings in the logs (micro tests)
            await self.send(AgentDoneMessage(text=spoken.strip(), timings=timings))

        except asyncio.CancelledError:
            # Keep completed ERP calls and their results. Unfinished model text was never played.
            # team 12 (Youssef): interrupted before any ERP call → the pieces stay in conv.pending and are merged
            # into the next turn (nothing forgotten, no half-question in the history). After ERP calls: keep them.
            if heard and not committed and working is not None and len(working) > history_size + 1:
                conv.history = trim_voice_turn(working, history_size, spoken)
                conv.pending = []
            if speaker:
                await speaker.stop()
            raise
        except Exception as e:
            if speaker:
                await speaker.stop()
            await self.send(VoiceErrorMessage(message=str(e) or type(e).__name__))
        finally:
            if utterance:
                utterance.cancel()  # interrupted while transcribing: close the provider stream


class Speaker:
    """Buffers the streamed text, cuts it into sentences and speaks them in order, as one audio segment."""

    # a sentence ends with . ! ? … followed by a space ("18.50" is not a boundary)
    SENTENCE = re.compile(r"^([\s\S]*?[.!?…])\s+")

    def __init__(
        self, tts: TTSClient, send: Callable[[WireModel], Awaitable],
        send_bytes: Callable[[bytes], Awaitable], bank: fillers.FillerBank | None = None,
    ):
        self.tts, self.send, self.send_bytes = tts, send, send_bytes
        self.bank = bank if bank is not None else fillers.FillerBank()
        self.acknowledged = False
        self.transcript_ready = False  # team 12: early_acknowledgement stops once the final transcript is there
        self.restatement: str | None = None
        self.quick_transcript: str | None = None
        self.waiting_task: asyncio.Task | None = None
        self._audio_lock = asyncio.Lock()
        self.social_turn = False
        self.first_phrase = True
        self.buffer = ""
        self.sentences: asyncio.Queue[str | None] = asyncio.Queue()
        self.worker: asyncio.Task | None = None  # speaks the queued sentences one after the other
        self.started = False
        self.first_byte_at: float | None = None
        self.tts_first_byte_ms: int | None = None
        self.audio_until = 0.0  # loop time when the audio already sent will have finished playing (mode 4 pacing)

    def push(self, delta: str) -> None:
        self.buffer += delta
        if team_flags.fillers() and self.first_phrase:
            clause = re.match(r"^([^.!?…,]{20,}?,)\s+", self.buffer)
            if clause:
                self.speak(clause[1])
                self.buffer = self.buffer[clause.end():]
        while m := self.SENTENCE.match(self.buffer):
            self.speak(m[1])
            self.buffer = self.buffer[m.end() :]

    def speak(self, sentence: str) -> None:
        if self.acknowledged and self.first_phrase:
            sentence = fillers.WAITING_LINE.sub("", sentence, count=1)
        if not sentence.strip():
            return
        self.first_phrase = False
        # Mode 4 keeps typing until the answer's first audio byte (cancelled in _speak_queued): no gap during the TTS.
        if self.waiting_task and not self.waiting_task.done() and not team_flags.no_silence():
            self.waiting_task.cancel()
        if self.worker is None:
            self.worker = asyncio.create_task(self._speak_queued())
        self.sentences.put_nowait(sentence)

    def start_waiting(self) -> None:
        self.waiting_task = asyncio.create_task(fillers.keep_waiting(self))

    async def stop_waiting(self) -> None:
        if self.waiting_task:
            self.waiting_task.cancel()
            await asyncio.gather(self.waiting_task, return_exceptions=True)

    async def play_audio(self, mime: str, data: bytes, seconds: float | None = None) -> None:
        if not data:
            return
        async with self._audio_lock:
            if not self.started:
                self.started = True
                await self.send(AgentAudioStartMessage(mime=mime))
                self.first_byte_at = time.perf_counter()
            await self.send_bytes(data)
            now = asyncio.get_running_loop().time()
            self.audio_until = max(now, self.audio_until) + (seconds if seconds is not None else fillers.mp3_seconds(data))

    async def finish(self) -> None:
        """Speak what is left in the buffer, wait for all the audio, close the segment."""
        if not team_flags.no_silence():
            await self.stop_waiting()
        self.speak(self.buffer)
        self.buffer = ""
        if self.worker:
            self.sentences.put_nowait(None)
            await self.worker
        await self.stop_waiting()  # mode 4: already stopped by the answer's first byte; no answer at all: stop now
        if self.started:
            await self.send(AgentAudioEndMessage())

    async def stop(self) -> None:
        """Interrupted: drop the queued sentences, close the segment if audio was sent."""
        await self.stop_waiting()
        if self.worker:
            self.worker.cancel()
            with suppress(asyncio.CancelledError):
                await self.worker
        if self.started:
            await self.send(AgentAudioEndMessage())

    async def _speak_queued(self) -> None:
        while (sentence := await self.sentences.get()) is not None:
            tts_start = time.perf_counter()
            try:
                result = await self.tts.synthesize(sentence, settings.tts.voice or None)
                # aclosing: on barge-in (cancellation) the provider's HTTP stream is closed right away
                async with aclosing(result.chunks) as chunks:  # type: ignore[type-var]
                    async for chunk in chunks:
                        if chunk and self.tts_first_byte_ms is None:
                            self.tts_first_byte_ms = ms_since(tts_start)
                        if chunk and self.waiting_task and not self.waiting_task.done():
                            await self.stop_waiting()  # mode 4: the answer is here, stop typing
                        await self.play_audio(result.mime, chunk)
            except Exception as e:
                await self.send(VoiceErrorMessage(message=f"TTS : {e}"))


def trim_voice_turn(messages: list[ChatMessage], history_size: int, reply: str) -> list[ChatMessage]:
    """Persist the user's turn, ERP calls and the same reply sent to audio."""
    history = messages[:history_size]
    for message in messages[history_size:]:
        if message.role != "assistant":
            history.append(message)
        elif message.tool_calls:
            history.append(message.model_copy(update={"content": ""}))
    if reply:
        history.append(ChatMessage(role="assistant", content=reply))
    return trim(history)


def trim(history: list[ChatMessage], max_messages: int = 40) -> list[ChatMessage]:
    """Keep the last ~40 messages, starting on a user message (never split a tool call from its result)."""
    history = sanitize_history(history)  # no dangling tool call (cancelled mid-tool), no orphan result
    if len(history) <= max_messages:
        return history
    start = next((i for i, m in enumerate(history) if i >= len(history) - max_messages and m.role == "user"), -1)
    return history[start:] if start > 0 else history

