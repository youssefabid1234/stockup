"""Youssef · hands-free made robust: no piece of speech lost, pieces merged, other voices and doubtful words marked."""

import asyncio
import json

import pytest

from app.agent import listening
from app.clients.base import STTUpdate, TTSResult
from app.clients.soniox import FINALIZE, SonioxSTT
from app.clients.ws import once
from app.schemas import ChatMessage, DoneEvent, TextEvent, ToolCall, ToolCallEvent, ToolResultEvent
from app.services import voice_session

from test_speech_providers import FakeWS, fake_connect  # noqa: E402  (the kit's fake Soniox socket)


# ── 1. annotate: Soniox tokens → transcript for the model ──


def tok(text, speaker="1", conf=0.95):
    return {"text": text, "speaker": speaker, "confidence": conf, "is_final": True}


def test_one_clear_voice_needs_no_mark():
    assert listening.annotate([tok("Trois"), tok(" cartons"), tok(" de"), tok(" tou"), tok("rage")]) is None


def test_a_background_voice_is_labelled_and_the_caller_is_the_main_voice():
    tokens = [tok("Il"), tok(" me"), tok(" faut"), tok(" trois"), tok(" cartons"),
              tok(" Tu", "2"), tok(" veux", "2"), tok(" un", "2"), tok(" café", "2"), tok(" ?", "2"),
              tok(" pour"), tok(" lundi")]  # fmt: skip
    assert listening.annotate(tokens) == "[appelant] Il me faut trois cartons [autre voix] Tu veux un café ? [appelant] pour lundi"


def test_a_doubtful_word_is_marked_even_when_only_one_of_its_pieces_is_unsure():
    tokens = [tok("Trois"), tok(" cartons"), tok(" de"), tok(" tou", conf=0.9), tok("ron", conf=0.3), tok(".")]
    assert listening.annotate(tokens) == "Trois cartons de touron(?)."


def test_control_tokens_and_empty_input():
    assert listening.annotate([{"text": "<end>"}, {"text": "<fin>"}]) is None
    assert listening.annotate([]) is None


# ── 2. merge_parts ──


def test_merge_keeps_every_piece_in_order():
    assert listening.merge_parts(["Il me faudrait du tourage", "", "3 cartons pour lundi, non mardi"]) == (
        "(L'appelant a parlé en 2 fois avant ta réponse, dans l'ordre :)\n1. Il me faudrait du tourage\n"
        "2. 3 cartons pour lundi, non mardi"
    )
    assert listening.merge_parts(["Bonjour"]) == "Bonjour"


def test_rule_is_only_for_the_phone():
    assert listening.listening_section("voice") and not listening.listening_section("chat")


# ── 3. Soniox: diarization asked, annotated final ──


async def test_soniox_asks_for_speakers_and_returns_the_annotated_final():
    ws = FakeWS(
        [
            {"tokens": [{"text": "Trois", "is_final": True, "speaker": "1", "confidence": 0.9}]},
            {"tokens": [{"text": " cartons", "is_final": True, "speaker": "1", "confidence": 0.9},
                        {"text": " café", "is_final": True, "speaker": "2", "confidence": 0.9},
                        {"text": "<fin>", "is_final": True}]},
        ],  # fmt: skip
        end=FINALIZE,
    )
    stt = SonioxSTT("sx", connect=fake_connect(ws, {}))
    updates = [u async for u in stt.transcribe_stream(once(b"a"), "audio/webm")]
    assert json.loads(ws.sent[0])["enable_speaker_diarization"] is True
    assert updates[-1] == STTUpdate("Trois cartons café", final=True, stable="Trois cartons café",
                                    annotated="[appelant] Trois cartons [autre voix] café")  # fmt: skip


# ── 4. voice session: pieces before the answer are merged, never lost ──


class Socket:
    def __init__(self):
        self.events = []

    async def send_text(self, message):
        self.events.append(json.loads(message))

    async def send_bytes(self, data):
        self.events.append(data)


class SilentTTS:
    name = "test"

    async def synthesize(self, text, voice=None):
        async def chunks():
            yield text.encode()

        return TTSResult("audio/mpeg", chunks())


@pytest.fixture
async def conn(monkeypatch):
    monkeypatch.delenv("TEAM_FILLERS", raising=False)
    monkeypatch.delenv("TEAM_ORCHESTRATOR", raising=False)
    monkeypatch.setattr(voice_session, "get_tts_client", lambda: SilentTTS())
    c = voice_session.VoiceConnection(Socket())
    await c.open()
    return c


async def test_a_second_piece_interrupting_the_thinking_is_answered_together_with_the_first(conn, monkeypatch):
    seen: list[str] = []
    thinking = asyncio.Event()

    async def agent(messages, **kw):
        seen.append(messages[-1].content)
        if len(seen) == 1:  # still thinking about the first piece when the caller goes on
            thinking.set()
            await asyncio.Event().wait()
        yield TextEvent(delta="D'accord.")
        yield DoneEvent(message=ChatMessage(role="assistant", content="D'accord."), ms=1)

    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.handle_text(json.dumps({"type": "text", "text": "Il me faudrait du tourage"}))
    await asyncio.wait_for(thinking.wait(), 2)
    await conn.handle_text(json.dumps({"type": "text", "text": "3 cartons pour mardi"}))
    await conn.turn
    assert "1. Il me faudrait du tourage" in seen[1] and "2. 3 cartons pour mardi" in seen[1]
    assert conn.conversation.pending == []  # answered
    users = [m.content for m in conn.conversation.history if m.role == "user"]
    assert len(users) == 1 and "Il me faudrait du tourage" in users[0]  # one question, not a dangling half


async def test_after_erp_calls_the_interrupted_piece_is_kept_in_the_history(conn, monkeypatch):
    started = asyncio.Event()

    async def agent(messages, **kw):
        if messages[-1].content == "Vous avez de la levure ?":
            call = ToolCall(id="s", name="search", arguments={})
            messages.append(ChatMessage(role="assistant", content="", tool_calls=[call]))
            messages.append(ChatMessage(role="tool", content="{}", tool_call_id="s"))
            yield ToolCallEvent(call=call)
            yield ToolResultEvent(call_id="s", name="search", ok=True, result={}, ms=1)
            started.set()
            await asyncio.Event().wait()
        yield DoneEvent(message=ChatMessage(role="assistant", content="Oui."), ms=1)

    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.handle_text(json.dumps({"type": "text", "text": "Vous avez de la levure ?"}))
    await asyncio.wait_for(started.wait(), 2)
    await conn.interrupt()
    assert conn.conversation.pending == []
    assert conn.conversation.history[0].content == "Vous avez de la levure ?"


async def test_a_piece_cut_while_being_transcribed_is_not_lost(conn):
    class SlowUtterance:
        frames = [b"x"]
        partial = "trois cartons de tourage"
        annotated = None

        async def text(self):
            await asyncio.Event().wait()

        def cancel(self):
            pass

    conn.start_turn(utterance=SlowUtterance())
    await asyncio.sleep(0.05)
    await conn.interrupt()
    assert conn.conversation.pending == ["trois cartons de tourage"]


async def test_hanging_up_forgets_what_was_pending(conn):
    conn.conversation.pending = ["trois cartons"]
    await conn.handle_text(json.dumps({"type": "reset"}))
    assert conn.conversation.pending == []
