"""Voice turn integration checks for Mohamed Amine's S10 and S11 scenarios."""
import asyncio
import json

import pytest

from app.clients.base import TTSResult
from app.clients.mock_speech import MockSTT
from app.schemas import TextEvent, ToolCall, ToolCallEvent
from app.services import fillers, vocabulary, voice_session


class Socket:
    def __init__(self):
        self.events = []

    async def send_text(self, message):
        self.events.append(json.loads(message))

    async def send_bytes(self, data):
        self.events.append(data)


class RecordingTTS:
    name = "test"

    def __init__(self):
        self.phrases = []

    async def synthesize(self, text, voice=None):
        self.phrases.append(text)

        async def chunks():
            yield text.encode()

        return TTSResult("audio/mpeg", chunks())


@pytest.fixture
async def call(monkeypatch):
    monkeypatch.setenv("TEAM_FILLERS", "1")
    monkeypatch.delenv("TEAM_ORCHESTRATOR", raising=False)
    tts = RecordingTTS()
    monkeypatch.setattr(voice_session, "get_tts_client", lambda: tts)
    monkeypatch.setattr(voice_session, "get_stt_client", lambda: MockSTT("merci"))
    conn = voice_session.VoiceConnection(Socket())
    await conn.open()
    await conn.audio_warm_up
    return conn, tts


async def test_lookup_plays_one_ack_one_click_and_one_answer(call, monkeypatch):
    conn, tts = call

    async def lookup(messages, **kwargs):
        for name in ("search", "get_price"):
            yield ToolCallEvent(call=ToolCall(id=name, name=name, arguments={}))
        yield TextEvent(delta="Un instant, je vérifie. Je regarde ce qu’il nous reste. La levure est disponible.")

    monkeypatch.setattr(voice_session, "run_agent", lookup)
    await conn.run_turn(conn.conversation, text="Vous avez de la levure en stock ?")
    events = conn.ws.events
    clips = [msg for msg in events if isinstance(msg, bytes)]
    assert clips[0].decode() in fillers.PHRASES["thinking"]
    assert clips[1:] == [fillers.keyboard_click(), "La levure est disponible.".encode()]
    assert tts.phrases == [*fillers.PHRASES["thinking"], "La levure est disponible."]
    assert sum(isinstance(m, dict) and m["type"] == "agent_audio_start" for m in events) == 1
    assert events[-2]["type"] == "agent_audio_end"
    assert events[-1]["timings"]["ttsFirstByteMs"] is not None


async def test_interruption_closes_old_audio_before_thanks(call, monkeypatch):
    conn, tts = call
    lookup_started = asyncio.Event()

    async def agent(messages, **kwargs):
        if messages[-1].content.startswith("Vous avez"):
            yield ToolCallEvent(call=ToolCall(id="lookup", name="search", arguments={}))
            lookup_started.set()
            await asyncio.Event().wait()
        # A model may still search on a goodbye. The voice layer must stay quiet.
        yield ToolCallEvent(call=ToolCall(id="extra", name="search", arguments={}))
        yield TextEvent(delta="Au revoir.")

    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.handle_text(json.dumps({"type": "text", "text": "Vous avez de la levure fraîche ?"}))
    await asyncio.wait_for(lookup_started.wait(), timeout=2)
    await conn.handle_text(json.dumps({"type": "audio_start", "mime": "audio/webm"}))
    assert conn.ws.events[-1]["type"] == "agent_audio_end"
    start = len(conn.ws.events)
    await conn.handle_text('{"type":"audio_end"}')
    await conn.turn
    assert [m for m in conn.ws.events[start:] if isinstance(m, bytes)] == [b"Au revoir."]
    assert conn.ws.events[-1]["type"] == "agent_done"


async def test_confirmed_lookup_with_no_early_match(call, monkeypatch):
    conn, _ = call

    async def lookup(messages, **kwargs):
        assert not any(isinstance(event, bytes) for event in conn.ws.events)
        yield ToolCallEvent(call=ToolCall(id="lookup", name="search", arguments={}))
        yield TextEvent(delta="La levure est disponible.")

    monkeypatch.setattr(voice_session, "run_agent", lookup)
    await conn.run_turn(conn.conversation, text="Il vous en reste de la levure ?")
    clips = [event for event in conn.ws.events if isinstance(event, bytes)]
    assert clips[0].decode() in fillers.PHRASES["thinking"]
    assert clips[1:] == ["La levure est disponible.".encode()]


async def test_failed_turn_closes_waiting_audio(call, monkeypatch):
    conn, _ = call

    async def fail(messages, **kwargs):
        yield ToolCallEvent(call=ToolCall(id="lookup", name="search", arguments={}))
        raise RuntimeError("ERP unavailable")

    monkeypatch.setattr(voice_session, "run_agent", fail)
    await conn.run_turn(conn.conversation, text="Vous avez de la levure en stock ?")
    assert conn.ws.events[-2]["type"] == "agent_audio_end"
    assert conn.ws.events[-1]["type"] == "error"


async def test_fast_agent_keeps_priority(call, monkeypatch):
    conn, tts = call
    monkeypatch.setenv("TEAM_ORCHESTRATOR", "1")
    speaker = voice_session.Speaker(tts, conn.send, conn.send_bytes, conn.bank)
    await fillers.on_turn_start(speaker, "Quel est le prix ?")
    assert not speaker.started
    speaker.push("Je vous écoute. ")
    await fillers.on_tool_call(speaker, "search")
    await speaker.finish()
    assert [event for event in conn.ws.events if isinstance(event, bytes)] == ["Je vous écoute.".encode()]


async def test_first_clause_starts_before_answer_ends(call):
    conn, tts = call
    speaker = voice_session.Speaker(tts, conn.send, conn.send_bytes, conn.bank)
    speaker.push("Pour votre prochaine livraison, ")
    await asyncio.sleep(0)
    assert tts.phrases[-1] == "Pour votre prochaine livraison,"
    speaker.push("le prix est de 18,50 euros.")
    await speaker.finish()
    assert tts.phrases[-1] == "le prix est de 18,50 euros."


async def test_company_terms_selects_contact_first_names(monkeypatch):
    class ERP:
        async def get(self, path, params):
            if path == "/api/clients":
                return [{"name": "Maison Sarrailh", "contacts": [{"name": "Nadine Sarrailh"}, {"name": ""}]}]
            return [{"name": "Farine", "aliases": ["Tradi"]}]

    vocabulary.reset_cache()
    try:
        monkeypatch.setenv("TEAM_FILLERS", "1")
        terms = await vocabulary.company_terms(ERP())
        assert terms[:6] == ["tradi", "tourage", "chocolatine", "gruau", "T55", "Nadine"]
        monkeypatch.delenv("TEAM_FILLERS")
        assert await vocabulary.company_terms(ERP()) == ["Maison Sarrailh", "Farine", "Tradi"]
    finally:
        vocabulary.reset_cache()


async def test_warm_up_retries_only_missing_clips():
    class FlakyTTS(RecordingTTS):
        async def synthesize(self, text, voice=None):
            if len(self.phrases) == 1:
                self.phrases.append(text)
                raise TimeoutError
            return await super().synthesize(text, voice)

    tts = FlakyTTS()
    bank = fillers.FillerBank()
    with pytest.raises(TimeoutError):
        await bank.warm_up(tts)
    assert len(bank.audio["thinking"]) == 1
    await bank.warm_up(tts)
    await bank.warm_up(tts)
    first, second = fillers.PHRASES["thinking"]
    assert tts.phrases == [first, second, second]


async def test_bakery_terms_remain_available_when_erp_is_down(monkeypatch):
    class UnavailableERP:
        async def get(self, path, params):
            raise TimeoutError

    vocabulary.reset_cache()
    try:
        monkeypatch.setenv("TEAM_FILLERS", "1")
        assert await vocabulary.company_terms(UnavailableERP()) == ["tradi", "tourage", "chocolatine", "gruau", "T55"]
        monkeypatch.delenv("TEAM_FILLERS")
        assert await vocabulary.company_terms(UnavailableERP()) == []
    finally:
        vocabulary.reset_cache()
