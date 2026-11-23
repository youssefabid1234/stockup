"""
WS /voice — push-to-talk voice sessions (messages: app/schemas/voice.py).

One turn:
    audio_start … binary frames … audio_end   (or a typed `text` message)
      → STT, live: each frame goes to the provider as it arrives (services/utterance.py);
        "transcript" final:false while the caller speaks, then "transcript" final:true soon after audio_end
      → agent (voice mode) streaming "agent_text" / "agent_tool"
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
from app.agent import run_agent, sanitize_history
from app.agent.call_context import CallContext
from app.agent.loop import ms_since
from app.agent.orchestrator import run_voice_turn
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
    ChatMessage,
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
from app.tools import all_tools

from . import fillers
from .utterance import Utterance
from .vocabulary import stt_hint

client_message = TypeAdapter(VoiceClientMessage)


@dataclass
class Conversation:
    id: str
    actor_name: str | None = None
    history: list[ChatMessage] = field(default_factory=list)
    call_context: CallContext | None = None  # team 12 (Youssef): the caller's sheet, once known (TEAM_PRELOAD)


# In memory: a reconnect with the same sessionId continues the conversation.
conversations: dict[str, Conversation] = {}


class VoiceConnection:
    """One WebSocket connection. Reads client messages; runs each turn as a background task."""

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.conversation: Conversation | None = None
        self.recording: Utterance | None = None  # while the key is down
        self.turn: asyncio.Task | None = None
        self.warm_up: asyncio.Task | None = None
        self.bank = fillers.FillerBank()
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
            case AudioEndMessage():
                if self.recording:
                    utterance, self.recording = self.recording, None
                    self.start_turn(utterance=utterance)
            case TextMessage(text=text):
                await self.interrupt()
                self.start_turn(text=text)
            case ResetMessage():
                await self.interrupt()
                self.conversation.history = []
                await self.open(self.conversation.id)

    async def send_partial(self, update: STTUpdate) -> None:
        await self.send(TranscriptMessage(text=update.text, final=False, stable=update.stable))

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

    def start_turn(self, **turn_input) -> None:
        self.turn = asyncio.create_task(self.run_turn(self.conversation, **turn_input))

    async def interrupt(self) -> None:
        """Barge-in: drop a recording in progress, stop the running turn and wait until it has cleaned up."""
        if self.recording:
            self.recording.cancel()
            self.recording = None
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
    ) -> None:
        t0 = time.perf_counter()  # end of caller speech
        timings = TurnTimings()
        heard, spoken = "", ""
        step_text = ""  # what the model said since the last tool result (not yet in `working`)
        working: list[ChatMessage] | None = None
        committed = False
        speaker: Speaker | None = None
        try:
            # 1. Speech → text: with a streaming STT only the last words are left to finalize
            if utterance is not None:
                text = await utterance.text()
                timings.stt_ms = ms_since(t0)  # end of speech → final transcript
            heard = (text or "").strip()
            if not heard:
                await self.send(VoiceErrorMessage(message="Rien entendu — réessayez."))
                return
            await self.send(TranscriptMessage(text=heard, final=True))

            # 2. Agent, on a working copy of the history (committed at the end)
            working = [*conv.history, ChatMessage(role="user", content=heard)]
            speaker = Speaker(get_tts_client(), self.send, self.send_bytes, self.bank)
            await fillers.on_turn_start(speaker, heard)  # team 12 (Mohamed Amine): no-op while TEAM_FILLERS is off
            llm_start = time.perf_counter()
            # team 12 (Youssef): the orchestrator when TEAM_ORCHESTRATOR is on, else the kit's agent loop
            agent = run_voice_turn if team_flags.orchestrator() else run_agent
            extra = {"call_context": conv.call_context} if conv.call_context is not None else {}
            async for ev in agent(working, llm=get_llm_client(), tools=all_tools(), mode="voice", actor_name=conv.actor_name, **extra):
                match ev:
                    case TextEvent(delta=delta):
                        if timings.llm_first_token_ms is None:
                            timings.llm_first_token_ms = ms_since(llm_start)
                        spoken += delta
                        step_text += delta
                        await self.send(AgentTextMessage(delta=delta))
                        speaker.push(delta)
                    case ToolCallEvent(call=call):
                        await self.send(AgentToolMessage(name=call.name, args=call.arguments))
                        await fillers.on_tool_call(speaker, call.name)  # team 12 (Mohamed Amine)
                    case ToolResultEvent(name=name, ok=ok, ms=ms):
                        step_text = ""
                        await self.send(AgentToolMessage(name=name, ok=ok, ms=ms))
                    case ErrorEvent(message=message):
                        await speaker.stop_waiting()
                        await self.send(VoiceErrorMessage(message=message))
            timings.llm_total_ms = ms_since(llm_start)
            conv.history = trim(working)
            committed = True

            # 3. Speak the last sentence and wait until all the audio is sent
            await speaker.finish()
            timings.tts_first_byte_ms = speaker.tts_first_byte_ms
            if speaker.first_byte_at:
                timings.total_ms = int((speaker.first_byte_at - t0) * 1000 + 0.5)
            await self.send(AgentDoneMessage(text=spoken.strip(), timings=timings))

        except asyncio.CancelledError:
            # Interrupted: keep what was heard, the tool rounds already done (an order the agent created must stay
            # known) and what the agent had started to say. Not when the turn was already committed (barge-in during
            # the last sentence's audio): that would duplicate it. trim() closes a tool call cut mid-run.
            if heard and not committed:
                kept = working if working is not None else [*conv.history, ChatMessage(role="user", content=heard)]
                last = kept[-1]
                if step_text.strip() and not (last.role == "assistant" and last.tool_calls):
                    kept = [*kept, ChatMessage(role="assistant", content=f"{step_text.strip()} …")]
                conv.history = trim(kept)
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
        self.restatement: str | None = None
        self.waiting_task: asyncio.Task | None = None
        self._audio_lock = asyncio.Lock()
        self.social_turn = False
        self.clicked = False
        self.first_phrase = True
        self.buffer = ""
        self.sentences: asyncio.Queue[str | None] = asyncio.Queue()
        self.worker: asyncio.Task | None = None  # speaks the queued sentences one after the other
        self.started = False
        self.first_byte_at: float | None = None
        self.tts_first_byte_ms: int | None = None

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
        if self.waiting_task and not self.waiting_task.done():
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

    async def play_audio(self, mime: str, data: bytes) -> None:
        if not data:
            return
        async with self._audio_lock:
            if not self.started:
                self.started = True
                await self.send(AgentAudioStartMessage(mime=mime))
                self.first_byte_at = time.perf_counter()
            await self.send_bytes(data)

    async def finish(self) -> None:
        """Speak what is left in the buffer, wait for all the audio, close the segment."""
        await self.stop_waiting()
        self.speak(self.buffer)
        self.buffer = ""
        if self.worker:
            self.sentences.put_nowait(None)
            await self.worker
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
                        await self.play_audio(result.mime, chunk)
            except Exception as e:
                await self.send(VoiceErrorMessage(message=f"TTS : {e}"))


def trim(history: list[ChatMessage], max_messages: int = 40) -> list[ChatMessage]:
    """Keep the last ~40 messages, starting on a user message (never split a tool call from its result)."""
    history = sanitize_history(history)  # no dangling tool call (cancelled mid-tool), no orphan result
    if len(history) <= max_messages:
        return history
    start = next((i for i, m in enumerate(history) if i >= len(history) - max_messages and m.role == "user"), -1)
    return history[start:] if start > 0 else history

