"""
Single-turn voice COMMAND (POST /command): a sales rep drives the ERP by voice.

    raw audio ──► STT ──┐            (POST /command: the whole recording after the release)
    live audio ─► STT ──┤            (WS /voice/command: streamed while the key is down, partial transcripts)
    typed text ─────────┴► transcript ──► agent (mode "command", NO history) ──► text / tool_call / tool_result
                                       ──► navigate  (only when the user asked to SEE something)
                                       ──► speech    (speak=1: TTS of the whole answer, base64)
                                       ──► done      (with timings)

Stateless on purpose: every utterance is a complete command ("crée une pré-commande pour Lemoine, 4 kilos de bar").
"""

import asyncio
import base64
import json
import re
import time
from collections.abc import AsyncIterator
from contextlib import aclosing, suppress
from dataclasses import dataclass

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from app.agent import run_agent
from app.agent.loop import ms_since
from app.clients import get_llm_client, get_stt_client, get_tts_client
from app.config import settings
from app.schemas import (
    ChatMessage,
    CommandStreamEvent,
    DoneEvent,
    ErrorEvent,
    NavigateEvent,
    SpeechEvent,
    TextEvent,
    ToolResultEvent,
    TranscriptEvent,
    TurnTimings,
)
from app.schemas.voice import AudioEndMessage, AudioStartMessage, TextMessage, VoiceClientMessage
from app.tools import all_tools
from app.tools.erp import enc

from .utterance import Utterance
from .vocabulary import stt_hint

# "montre-moi le stock de turbot", "ouvre la fiche de Lemoine", "affiche la commande …"
VIEW_INTENT = re.compile(r"\b(montre|montrez|affiche|affichez|ouvre|ouvrez|ouvrir|voir|vois|regarde|va sur|va à|aller sur|fiche)\b", re.I | re.A)  # fmt: skip

# Web app route of an entity, by its type (search hits) or by its id prefix.
ROUTE_BY_TYPE = {"client": "/clients/", "product": "/products/", "order": "/orders/", "supplier": "/suppliers/", "invoice": "/invoices/"}  # fmt: skip
ROUTE_BY_PREFIX = [
    (r"^cli_", "/clients/"),
    (r"^prd_", "/products/"),
    (r"^(ord|cmd)_", "/orders/"),
    (r"^inv_", "/invoices/"),
    (r"^(sup|frn)_", "/suppliers/"),
    (r"^po_", "/purchase-orders/"),
]


@dataclass
class Entity:
    path: str
    label: str | None


def entity_of(result) -> Entity | None:
    """The web page of an entity seen in a tool result (an object with an id, or the top search hit)."""
    r = (result[0] if result else None) if isinstance(result, list) else result
    if not isinstance(r, dict) or not isinstance(r.get("id"), str):
        return None
    base = ROUTE_BY_TYPE.get(r.get("type")) if isinstance(r.get("type"), str) else None
    base = base or next((route for prefix, route in ROUTE_BY_PREFIX if re.match(prefix, r["id"])), None)
    if not base:
        return None
    label = next((r[k] for k in ("number", "name", "label") if isinstance(r.get(k), str)), None)
    return Entity(path=base + enc(r["id"]), label=label)


async def run_command(
    *,
    text: str | None = None,  # typed command…
    audio: bytes | None = None,  # …or a recording…
    utterance: Utterance | None = None,  # …or a live recording, transcribed while it was recorded
    mime: str = "audio/webm",
    hint: str | None = None,  # STT vocabulary hint (mock STT: the transcript)
    actor_name: str = "Commande vocale",
    speak: bool = False,
) -> AsyncIterator[CommandStreamEvent]:
    t0 = time.perf_counter()
    timings = TurnTimings()

    # 1. Speech → text
    if audio is not None or utterance is not None:
        try:
            if utterance is not None:
                text = await utterance.text()  # t0 = the release: only the last words were left
            else:
                stt = get_stt_client()
                text = await stt.transcribe(audio or b"", mime, await stt_hint(stt.name, hint))
        except Exception as e:
            yield ErrorEvent(message=f"STT : {e}")
            return
        timings.stt_ms = ms_since(t0)
    text = (text or "").strip()
    yield TranscriptEvent(text=text, ms=timings.stt_ms or 0)
    if not text:
        yield ErrorEvent(message="Rien entendu — réessayez.")
        return

    # 2. Agent, stateless: the history is this one utterance.
    llm_start = time.perf_counter()
    answer = ""
    last_entity: Entity | None = None
    done: DoneEvent | None = None
    messages = [ChatMessage(role="user", content=text)]
    async for ev in run_agent(messages, llm=get_llm_client(), tools=all_tools(), mode="command", actor_name=actor_name):
        if isinstance(ev, TextEvent):
            if timings.llm_first_token_ms is None:
                timings.llm_first_token_ms = ms_since(llm_start)
            answer += ev.delta
        elif isinstance(ev, ToolResultEvent) and ev.ok:
            last_entity = entity_of(ev.result) or last_entity
        if isinstance(ev, DoneEvent):
            done = ev  # sent last, with the timings
        else:
            yield ev
    timings.llm_total_ms = ms_since(llm_start)
    if not done:
        return  # the error was already streamed

    # 3. "montre-moi …" → let the UI open what was looked at.
    if last_entity and VIEW_INTENT.search(text):
        yield NavigateEvent(path=last_entity.path, label=last_entity.label)

    # 4. Optional TTS of the whole (one-line) answer.
    say = (done.message.content or answer).strip()
    if speak and say:
        tts_start = time.perf_counter()
        try:
            result = await get_tts_client().synthesize(say, settings.tts.voice or None)
            audio_out = b""
            async with aclosing(result.chunks) as chunks:  # type: ignore[type-var]
                async for chunk in chunks:
                    if timings.tts_first_byte_ms is None:
                        timings.tts_first_byte_ms = ms_since(tts_start)
                    audio_out += chunk
            yield SpeechEvent(mime=result.mime, audio=base64.b64encode(audio_out).decode(), ms=ms_since(tts_start))
        except Exception as e:
            yield ErrorEvent(message=f"TTS : {e}")

    timings.total_ms = ms_since(t0)
    done.timings = timings
    yield done



command_message = TypeAdapter(VoiceClientMessage)


async def serve_command_ws(ws: WebSocket, speak: bool = False) -> None:
    """
    WS /voice/command[?speak=1]: the same single command, with the audio streamed while the key is down.

        → audio_start {mime, hint?} · binary frames (every 100–250 ms) · audio_end      (or one `text` message)
        ← transcript {final: false, stable} … while speaking, then the POST /command events (transcript final, …, done)

    One command per connection: the server closes it after `done` / `error`. Closing it earlier cancels the command
    (and the provider's STT stream).
    """
    await ws.accept()

    async def send(event) -> None:
        with suppress(WebSocketDisconnect, RuntimeError):  # the client is gone: nothing to do
            await ws.send_text(event.to_json())

    async def answer(**command_input) -> None:
        async with aclosing(run_command(speak=speak, **command_input)) as events:
            async for event in events:
                await send(event)
        with suppress(RuntimeError):
            await ws.close()

    utterance: Utterance | None = None
    runner: asyncio.Task | None = None
    try:
        while True:
            frame = await ws.receive()
            if frame["type"] == "websocket.disconnect":
                break
            if frame.get("bytes") is not None:
                if utterance and not runner:
                    utterance.feed(frame["bytes"])
                continue
            try:
                msg = command_message.validate_python(json.loads(frame.get("text") or ""))
            except (json.JSONDecodeError, ValidationError):
                await send(ErrorEvent(message="invalid JSON message"))
                continue
            if runner:
                continue  # one command per connection
            match msg:
                case AudioStartMessage(mime=mime, hint=hint) if not utterance:
                    partial = lambda u: send(TranscriptEvent(text=u.text, ms=0, final=False, stable=u.stable))  # noqa: E731
                    utterance = Utterance(get_stt_client(), mime, hint, on_partial=partial)
                case AudioEndMessage() if utterance:
                    runner = asyncio.create_task(answer(utterance=utterance, mime=utterance.mime))
                case TextMessage(text=text):
                    runner = asyncio.create_task(answer(text=text))
    except WebSocketDisconnect:
        pass
    finally:
        if runner and not runner.done():
            runner.cancel()
            with suppress(asyncio.CancelledError):
                await runner
        if utterance:
            utterance.cancel()
