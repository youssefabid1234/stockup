"""Voice turn integration checks for Mohamed Amine's S10 and S11 scenarios."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from app import team_flags
from app.clients.base import LLMText, TTSResult
from app.clients.mock_speech import MockSTT
from app.schemas import ChatMessage, DoneEvent, TextEvent, ToolCall, ToolCallEvent
from app.services import fast_restatement, fillers, vocabulary, voice_session
from app.services.voice_reply import spoken_reply


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
async def call(monkeypatch, request):
    monkeypatch.setenv("TEAM_FILLERS", getattr(request, "param", "1"))
    monkeypatch.delenv("TEAM_ORCHESTRATOR", raising=False)
    tts = RecordingTTS()
    monkeypatch.setattr(voice_session, "get_tts_client", lambda: tts)
    monkeypatch.setattr(voice_session, "get_stt_client", lambda: MockSTT("merci"))
    conn = voice_session.VoiceConnection(Socket())
    await conn.open()
    await conn.audio_warm_up
    return conn, tts


async def test_fast_lookup_plays_one_ack_and_one_answer(call, monkeypatch):
    conn, tts = call

    async def lookup(messages, **kwargs):
        for name in ("search", "get_price"):
            yield ToolCallEvent(call=ToolCall(id=name, name=name, arguments={}))
        yield TextEvent(delta="Un instant, je vérifie. Je regarde ce qu’il nous reste. La levure est disponible.")
        yield DoneEvent(message=ChatMessage(role="assistant", content="Un instant, je vérifie. Je regarde ce qu’il nous reste. La levure est disponible."), ms=1)

    monkeypatch.setattr(voice_session, "run_agent", lookup)
    await conn.run_turn(conn.conversation, text="Vous avez de la levure en stock ?")
    events = conn.ws.events
    clips = [msg for msg in events if isinstance(msg, bytes)]
    assert clips[0].decode() in fillers.PHRASES["thinking"]
    assert clips[1:] == ["La levure est disponible.".encode()]
    assert tts.phrases == [*fillers.PHRASES["thinking"], *fillers.PHRASES["follow_up"], "La levure est disponible."]
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
        yield DoneEvent(message=ChatMessage(role="assistant", content="Au revoir."), ms=1)

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
        yield DoneEvent(message=ChatMessage(role="assistant", content="La levure est disponible."), ms=1)

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
    assert tts.phrases == [first, second, second, *fillers.PHRASES["follow_up"]]


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


async def test_following_order_gets_waiting_audio_until_the_answer(call, monkeypatch):
    conn, _ = call
    monkeypatch.setattr(fillers, "FIRST_KEYBOARD_DELAY", 0)
    monkeypatch.setattr(fillers, "FOLLOW_UP_DELAY", 0)
    monkeypatch.setattr(fillers, "KEYBOARD_INTERVAL", 0.01)
    restatement = "Pour 10 kg de farine t55.".encode()
    restatement_played = asyncio.Event()
    original_send = conn.ws.send_bytes

    async def observe_audio(data):
        await original_send(data)
        if data == restatement:
            restatement_played.set()

    async def agent(messages, **kwargs):
        if messages[-1].content.startswith("Ajoutez"):
            yield TextEvent(delta="Je vais regarder.")
            yield ToolCallEvent(call=ToolCall(id="search", name="search", arguments={}))
            await asyncio.wait_for(restatement_played.wait(), timeout=2)
            yield TextEvent(delta=" La farine est disponible pour jeudi.")
            yield DoneEvent(message=ChatMessage(role="assistant", content=" La farine est disponible pour jeudi."), ms=1)
        else:
            yield TextEvent(delta="On a de la levure.")
            yield DoneEvent(message=ChatMessage(role="assistant", content="On a de la levure."), ms=1)

    monkeypatch.setattr(conn.ws, "send_bytes", observe_audio)
    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.run_turn(conn.conversation, text="Vous avez de la levure en stock ?")
    first_clips = [event for event in conn.ws.events if isinstance(event, bytes)]
    assert first_clips[0].decode() in fillers.PHRASES["thinking"]
    start = len(conn.ws.events)
    await conn.run_turn(conn.conversation, text="Ajoutez 10kg de farine T55 pour jeudi.")
    await asyncio.sleep(0.025)
    clips = [event for event in conn.ws.events[start:] if isinstance(event, bytes)]
    assert clips[0].decode() in fillers.PHRASES["thinking"]
    assert clips[1:] == [fillers.keyboard_click(), restatement, "La farine est disponible pour jeudi.".encode()]
    assert conn.ws.events[-2]["type"] == "agent_audio_end"


@pytest.mark.parametrize(
    ("heard", "expected"),
    [
        ("Je veux 10kg de farine", "Pour 10 kg de farine."),
        ("Et deux sacs de farine pour jeudi ?", "Pour deux sacs de farine."),
        ("10 kg de farine ou de sucre", None),
        ("10 kg de farine, finalement 20 kg de sucre", None),
        ("10 kg de farine et deux sacs de sucre", None),
        ("Je ne veux pas 10 kg de farine", None),
        ("C'est tout, merci.", None),
    ],
)
def test_restatement_uses_only_an_unambiguous_quantity(heard, expected):
    assert fillers.quantity_restatement(heard) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("<think>Il me faut le stock.</think>Bonjour, je vous écoute.", "Bonjour, je vous écoute."),
    ("Je dois vérifier l’ERP. Réponse : Bonjour, on a du stock.", "Bonjour, on a du stock."),
    ("Analyse : je dois chercher.", ""),
    ("Bonjour. Il reste 12,5 kilos de farine.", "Bonjour. Il reste 12,5 kilos de farine."),
    ("Je vous confirme la date de jeudi.", "Je vous confirme la date de jeudi."),
])
def test_spoken_reply_removes_internal_preamble(raw, expected):
    assert spoken_reply(raw) == expected


@pytest.mark.parametrize(("value", "enabled", "fast"), [("0", False, False), ("1", True, False), ("2", True, True)])
def test_waiting_modes_are_separate(monkeypatch, value, enabled, fast):
    monkeypatch.setenv("TEAM_FILLERS", value)
    assert team_flags.fillers() is enabled
    assert team_flags.fast_fillers() is fast


@pytest.mark.parametrize(("heard", "selection", "expected"), [
    ("Euh, je veux 10 kg de farine pour demain", "je veux 10 kg de farine pour demain",
     "Vous avez notamment dit : je veux 10 kg de farine pour demain."),
    ("10 kg de farine ou deux sacs, je ne sais plus", "10 kg de farine",
     "Vous disiez : 10 kg de farine ou deux sacs, je ne sais plus."),
    ("Je veux 10,5 kg de farine", "5 kg de farine", "Vous disiez : Je veux 10,5 kg de farine."),
    ("Je veux 10 kg de farine", "Je veux 20 kg de farine", "Vous disiez : Je veux 10 kg de farine."),
    ("Peut-être jeudi, mais lundi irait aussi", "", "Vous disiez : Peut-être jeudi, mais lundi irait aussi."),
])
async def test_fast_model_selection_keeps_customer_words(monkeypatch, heard, selection, expected):
    async def model_excerpt(transcript):
        assert transcript == heard
        return selection

    monkeypatch.setattr(fast_restatement, "_model_excerpt", model_excerpt)
    assert await fast_restatement.fast_restatement(heard) == expected


@pytest.mark.parametrize("call", ["2"], indirect=True)
async def test_fast_mode_reads_back_ambiguous_turn_while_agent_works(call, monkeypatch):
    conn, _ = call
    monkeypatch.setattr(fillers, "FAST_INTRO_DELAY", 0)
    monkeypatch.setattr(fillers, "FAST_RESTATEMENT_DELAY", 0)
    monkeypatch.setattr(fast_restatement, "settings", SimpleNamespace(llm=SimpleNamespace(provider="anthropic")))
    caller_text = "Plutôt celui de lundi ou le petit format, je ne sais plus"
    recap = f"Vous disiez : {caller_text}.".encode()
    reply = "Vous parlez de la farine ?"
    main_work_started = asyncio.Event()
    recap_played = asyncio.Event()
    model_calls = []
    original_send = conn.ws.send_bytes

    class FastLLM:
        async def stream(self, request):
            assert main_work_started.is_set()
            model_calls.append(request)
            yield LLMText("celui de lundi")

    async def observe_audio(data):
        await original_send(data)
        if data == recap:
            recap_played.set()

    async def agent(messages, **kwargs):
        assert [m.content for m in messages] == [caller_text]
        main_work_started.set()
        yield TextEvent(delta="Je dois identifier le produit. ")
        yield ToolCallEvent(call=ToolCall(id="search", name="search", arguments={}))
        await asyncio.wait_for(recap_played.wait(), timeout=2)
        yield TextEvent(delta=reply)
        yield DoneEvent(message=ChatMessage(role="assistant", content=reply), ms=1)

    monkeypatch.setattr(fast_restatement, "get_fast_llm_client", FastLLM)
    monkeypatch.setattr(conn.ws, "send_bytes", observe_audio)
    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.run_turn(conn.conversation, text=caller_text)

    assert len(model_calls) == 1
    assert not model_calls[0].tools
    assert [m.content for m in model_calls[0].messages] == [caller_text]
    assert [msg for msg in conn.ws.events if isinstance(msg, bytes)] == [b"Je vais voir.", recap, reply.encode()]
    assert [msg["delta"] for msg in conn.ws.events if isinstance(msg, dict) and msg["type"] == "agent_text"] == [reply]
    assert conn.ws.events[-1]["text"] == reply


@pytest.mark.parametrize("call", ["2"], indirect=True)
async def test_fast_mode_cancels_the_restatement_when_answer_is_ready(call, monkeypatch):
    conn, _ = call
    started = asyncio.Event()
    cancelled = asyncio.Event()
    reply = "Il reste de la farine."

    async def waiting_restatement(heard):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def agent(messages, **kwargs):
        await asyncio.wait_for(started.wait(), timeout=2)
        yield TextEvent(delta=reply)
        yield DoneEvent(message=ChatMessage(role="assistant", content=reply), ms=1)

    monkeypatch.setattr(fillers, "fast_restatement", waiting_restatement)
    monkeypatch.setattr(voice_session, "run_agent", agent)
    await asyncio.wait_for(conn.run_turn(conn.conversation, text="Vous avez de la farine en stock ?"), timeout=2)
    assert cancelled.is_set()
    assert [msg for msg in conn.ws.events if isinstance(msg, bytes)] == [b"Je vais voir.", reply.encode()]


@pytest.mark.parametrize("call", ["2"], indirect=True)
async def test_fast_mode_keeps_thanks_direct(call, monkeypatch):
    conn, _ = call
    calls = []

    async def waiting_restatement(heard):
        calls.append(heard)

    async def agent(messages, **kwargs):
        yield TextEvent(delta="Au revoir.")
        yield DoneEvent(message=ChatMessage(role="assistant", content="Au revoir."), ms=1)

    monkeypatch.setattr(fillers, "FAST_INTRO_DELAY", 0)
    monkeypatch.setattr(fillers, "fast_restatement", waiting_restatement)
    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.run_turn(conn.conversation, text="C'est tout, merci.")
    assert calls == []
    assert [msg for msg in conn.ws.events if isinstance(msg, bytes)] == [b"Au revoir."]


@pytest.mark.parametrize("call", ["2"], indirect=True)
async def test_barge_in_cancels_fast_model_before_it_can_speak(call, monkeypatch):
    conn, _ = call
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def waiting_restatement(heard):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    async def agent(messages, **kwargs):
        yield ToolCallEvent(call=ToolCall(id="search", name="search", arguments={}))
        await asyncio.Event().wait()

    monkeypatch.setattr(fillers, "fast_restatement", waiting_restatement)
    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.handle_text(json.dumps({"type": "text", "text": "Vous avez de la farine en stock ?"}))
    await asyncio.wait_for(started.wait(), timeout=2)
    await conn.handle_text(json.dumps({"type": "audio_start", "mime": "audio/webm"}))
    assert cancelled.is_set()
    assert [msg for msg in conn.ws.events if isinstance(msg, bytes)] == [b"Je vais voir."]
    assert conn.ws.events[-1]["type"] == "agent_audio_end"
    await conn.interrupt()
