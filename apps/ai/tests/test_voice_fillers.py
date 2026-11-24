"""Voice turn integration checks for Mohamed Amine's S10 and S11 scenarios."""
import asyncio
import json
from types import SimpleNamespace

import pytest

from app import team_flags
from app.agent import orchestrator
from app.agent.call_context import CallContext
from app.clients.base import LLMText, TTSResult
from app.clients.mock_speech import MockSTT
from app.schemas import CallerMessage, ChatMessage, DoneEvent, TextEvent, ToolCall, ToolCallEvent
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
    monkeypatch.setattr(voice_session, "get_stt_client", lambda: MockSTT("thanks"))
    conn = voice_session.VoiceConnection(Socket())
    await conn.open()
    if conn.audio_warm_up:
        await conn.audio_warm_up
    return conn, tts


async def test_fast_lookup_plays_one_ack_and_one_answer(call, monkeypatch):
    conn, tts = call

    async def lookup(messages, **kwargs):
        for name in ("search", "get_price"):
            yield ToolCallEvent(call=ToolCall(id=name, name=name, arguments={}))
        yield TextEvent(delta="One moment, I'm checking. Let me check. The yeast is available.")
        yield DoneEvent(message=ChatMessage(role="assistant", content="One moment, I'm checking. Let me check. The yeast is available."), ms=1)

    monkeypatch.setattr(voice_session, "run_agent", lookup)
    await conn.run_turn(conn.conversation, text="Do you have yeast in stock?")
    events = conn.ws.events
    clips = [msg for msg in events if isinstance(msg, bytes)]
    assert clips[0].decode() in fillers.PHRASES["thinking"]
    assert clips[1:] == ["The yeast is available.".encode()]
    assert tts.phrases == [*fillers.PHRASES["thinking"], *fillers.PHRASES["follow_up"], "The yeast is available."]
    assert sum(isinstance(m, dict) and m["type"] == "agent_audio_start" for m in events) == 1
    assert events[-2]["type"] == "agent_audio_end"
    assert events[-1]["timings"]["ttsFirstByteMs"] is not None


async def test_interruption_closes_old_audio_before_thanks(call, monkeypatch):
    conn, tts = call
    lookup_started = asyncio.Event()

    async def agent(messages, **kwargs):
        if messages[-1].content.startswith("Do you have"):
            yield ToolCallEvent(call=ToolCall(id="lookup", name="search", arguments={}))
            lookup_started.set()
            await asyncio.Event().wait()
        # A model may still search on a goodbye. The voice layer must stay quiet.
        yield ToolCallEvent(call=ToolCall(id="extra", name="search", arguments={}))
        yield TextEvent(delta="Goodbye.")
        yield DoneEvent(message=ChatMessage(role="assistant", content="Goodbye."), ms=1)

    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.handle_text(json.dumps({"type": "text", "text": "Do you have fresh yeast?"}))
    await asyncio.wait_for(lookup_started.wait(), timeout=2)
    await conn.handle_text(json.dumps({"type": "audio_start", "mime": "audio/webm"}))
    assert conn.ws.events[-1]["type"] == "agent_audio_end"
    start = len(conn.ws.events)
    await conn.handle_text('{"type":"audio_end"}')
    await conn.turn
    assert [m for m in conn.ws.events[start:] if isinstance(m, bytes)] == [b"Goodbye."]
    assert conn.ws.events[-1]["type"] == "agent_done"


async def test_confirmed_lookup_with_no_early_match(call, monkeypatch):
    conn, _ = call

    async def lookup(messages, **kwargs):
        assert not any(isinstance(event, bytes) for event in conn.ws.events)
        yield ToolCallEvent(call=ToolCall(id="lookup", name="search", arguments={}))
        yield TextEvent(delta="The yeast is available.")
        yield DoneEvent(message=ChatMessage(role="assistant", content="The yeast is available."), ms=1)

    monkeypatch.setattr(voice_session, "run_agent", lookup)
    await conn.run_turn(conn.conversation, text="And the yeast?")
    clips = [event for event in conn.ws.events if isinstance(event, bytes)]
    assert clips[0].decode() in fillers.PHRASES["thinking"]
    assert clips[1:] == ["The yeast is available.".encode()]


async def test_failed_turn_closes_waiting_audio(call, monkeypatch):
    conn, _ = call

    async def fail(messages, **kwargs):
        yield ToolCallEvent(call=ToolCall(id="lookup", name="search", arguments={}))
        raise RuntimeError("ERP unavailable")

    monkeypatch.setattr(voice_session, "run_agent", fail)
    await conn.run_turn(conn.conversation, text="Do you have yeast in stock?")
    assert conn.ws.events[-2]["type"] == "agent_audio_end"
    assert conn.ws.events[-1]["type"] == "error"


async def test_current_orchestrator_keeps_announcements_enabled(call, monkeypatch):
    conn, _ = call
    monkeypatch.setenv("TEAM_ORCHESTRATOR", "1")
    reply = "It costs two euros per kilo."

    async def agent(messages, **kwargs):
        yield ToolCallEvent(call=ToolCall(id="price", name="get_price", arguments={}))
        yield TextEvent(delta=reply)
        yield DoneEvent(message=ChatMessage(role="assistant", content=reply), ms=1)

    monkeypatch.setattr(orchestrator, "run_agent", agent)
    await conn.run_turn(conn.conversation, text="What is the price?")
    clips = [event for event in conn.ws.events if isinstance(event, bytes)]
    assert clips[0].decode() in fillers.PHRASES["thinking"]
    assert clips[1:] == [reply.encode()]


async def test_first_clause_starts_before_answer_ends(call):
    conn, tts = call
    speaker = voice_session.Speaker(tts, conn.send, conn.send_bytes, conn.bank)
    speaker.push("For your next delivery, ")
    await asyncio.sleep(0)
    assert tts.phrases[-1] == "For your next delivery,"
    speaker.push("le prix est de 18.50 euros.")
    await speaker.finish()
    assert tts.phrases[-1] == "le prix est de 18.50 euros."


async def test_company_terms_selects_contact_first_names(monkeypatch):
    class ERP:
        async def get(self, path, params):
            if path == "/api/clients":
                return [{"name": "Maison Sarrailh", "contacts": [{"name": "Nadine Sarrailh"}, {"name": ""}]}]
            return [{"name": "Flour", "aliases": ["Traditional"]}]

    vocabulary.reset_cache()
    try:
        monkeypatch.setenv("TEAM_FILLERS", "1")
        terms = await vocabulary.company_terms(ERP())
        assert terms[:6] == ["traditional flour", "laminating butter", "pain au chocolat", "strong flour", "T55", "Nadine"]
        monkeypatch.delenv("TEAM_FILLERS")
        assert await vocabulary.company_terms(ERP()) == ["Maison Sarrailh", "Flour", "Traditional"]
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
        assert await vocabulary.company_terms(UnavailableERP()) == ["traditional flour", "laminating butter", "pain au chocolat", "strong flour", "T55"]
        monkeypatch.delenv("TEAM_FILLERS")
        assert await vocabulary.company_terms(UnavailableERP()) == []
    finally:
        vocabulary.reset_cache()


async def test_following_order_gets_waiting_audio_until_the_answer(call, monkeypatch):
    conn, _ = call
    monkeypatch.setattr(fillers, "FIRST_KEYBOARD_DELAY", 0)
    monkeypatch.setattr(fillers, "FOLLOW_UP_DELAY", 0)
    monkeypatch.setattr(fillers, "KEYBOARD_INTERVAL", 0.01)
    restatement = "For 10 kg of t55 flour.".encode()
    restatement_played = asyncio.Event()
    original_send = conn.ws.send_bytes

    async def observe_audio(data):
        await original_send(data)
        if data == restatement:
            restatement_played.set()

    async def agent(messages, **kwargs):
        if messages[-1].content.startswith("Add"):
            yield TextEvent(delta="Let me check.")
            yield ToolCallEvent(call=ToolCall(id="search", name="search", arguments={}))
            await asyncio.wait_for(restatement_played.wait(), timeout=2)
            yield TextEvent(delta=" The flour is available for Thursday.")
            yield DoneEvent(message=ChatMessage(role="assistant", content=" The flour is available for Thursday."), ms=1)
        else:
            yield TextEvent(delta="We have yeast.")
            yield DoneEvent(message=ChatMessage(role="assistant", content="We have yeast."), ms=1)

    monkeypatch.setattr(conn.ws, "send_bytes", observe_audio)
    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.run_turn(conn.conversation, text="Do you have yeast in stock?")
    first_clips = [event for event in conn.ws.events if isinstance(event, bytes)]
    assert first_clips[0].decode() in fillers.PHRASES["thinking"]
    start = len(conn.ws.events)
    await conn.run_turn(conn.conversation, text="Add 10kg of T55 flour for Thursday.")
    await asyncio.sleep(0.025)
    clips = [event for event in conn.ws.events[start:] if isinstance(event, bytes)]
    assert clips[0].decode() in fillers.PHRASES["thinking"]
    assert clips[1:] == [fillers.keyboard_click(), restatement, "The flour is available for Thursday.".encode()]
    assert conn.ws.events[-2]["type"] == "agent_audio_end"


@pytest.mark.parametrize(
    ("heard", "expected"),
    [
        ("I want 10kg of flour", "For 10 kg of flour."),
        ("And two sacks of flour for Thursday?", "For two sacks of flour."),
        ("10 kg of flour or sugar", None),
        ("10 kg of flour, actually 20 kg of sugar", None),
        ("10 kg of flour and two sacks of sugar", None),
        ("I do not want 10 kg of flour", None),
        ("That's all, thanks.", None),
    ],
)
def test_restatement_uses_only_an_unambiguous_quantity(heard, expected):
    assert fillers.quantity_restatement(heard) == expected


@pytest.mark.parametrize(("raw", "expected"), [
    ("<think>I need the stock.</think>Hello, how can I help?", "Hello, how can I help?"),
    ("I need to check the ERP. Answer: Hello, we have stock.", "Hello, we have stock."),
    ("Analysis: I need to search.", ""),
    ("Hello. There are 12.5 kilos of flour left.", "Hello. There are 12.5 kilos of flour left."),
    ("I can confirm delivery on Thursday.", "I can confirm delivery on Thursday."),
])
def test_spoken_reply_removes_internal_preamble(raw, expected):
    assert spoken_reply(raw) == expected


@pytest.mark.parametrize(("value", "enabled", "fast"), [("0", False, False), ("1", True, False), ("2", True, True), ("3", True, True)])
def test_waiting_modes_are_separate(monkeypatch, value, enabled, fast):
    monkeypatch.setenv("TEAM_FILLERS", value)
    assert team_flags.fillers() is enabled
    assert team_flags.fast_fillers() is fast


@pytest.mark.parametrize(("heard", "selection", "expected"), [
    ("Um, I want 10 kg of flour for tomorrow", "I want 10 kg of flour for tomorrow",
     "You said, in particular: I want 10 kg of flour for tomorrow."),
    ("10 kg of flour or two sacks, I'm not sure", "10 kg of flour",
     "You said: 10 kg of flour or two sacks, I'm not sure."),
    ("I want 10.5 kg of flour", "5 kg of flour", "You said: I want 10.5 kg of flour."),
    ("I want 10 kg of flour", "I want 20 kg of flour", "You said: I want 10 kg of flour."),
    ("Maybe Thursday, but Monday would work too", "", "You said: Maybe Thursday, but Monday would work too."),
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
    caller_text = "Maybe the Monday one or the smaller size, I'm not sure"
    recap = f"You said: {caller_text}.".encode()
    reply = "Do you mean flour?"
    main_work_started = asyncio.Event()
    recap_played = asyncio.Event()
    model_calls = []
    original_send = conn.ws.send_bytes

    class FastLLM:
        async def stream(self, request):
            assert main_work_started.is_set()
            model_calls.append(request)
            yield LLMText("the Monday one")

    async def observe_audio(data):
        await original_send(data)
        if data == recap:
            recap_played.set()

    async def agent(messages, **kwargs):
        assert [m.content for m in messages] == [caller_text]
        main_work_started.set()
        yield TextEvent(delta="I need to identify the product. ")
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
    assert [msg for msg in conn.ws.events if isinstance(msg, bytes)] == [b"I'll take a look.", recap, reply.encode()]
    assert [msg["delta"] for msg in conn.ws.events if isinstance(msg, dict) and msg["type"] == "agent_text"] == [reply]
    assert conn.ws.events[-1]["text"] == reply


@pytest.mark.parametrize("call", ["2", "3"], indirect=True)
async def test_fast_mode_cancels_the_restatement_when_answer_is_ready(call, monkeypatch):
    conn, _ = call
    started = asyncio.Event()
    cancelled = asyncio.Event()
    reply = "We have flour left."

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
    await asyncio.wait_for(conn.run_turn(conn.conversation, text="Do you have flour in stock?"), timeout=2)
    assert cancelled.is_set()
    clips = [msg for msg in conn.ws.events if isinstance(msg, bytes)]
    announcements = [fillers.FAST_INTRO] if team_flags.fillers_mode() == 2 else fillers.PHRASES["thinking"]
    assert clips[0].decode() in announcements
    assert clips[1:] == [reply.encode()]


@pytest.mark.parametrize("call", ["2", "3"], indirect=True)
async def test_fast_mode_keeps_thanks_direct(call, monkeypatch):
    conn, _ = call
    calls = []

    async def waiting_restatement(heard):
        calls.append(heard)

    async def agent(messages, **kwargs):
        yield TextEvent(delta="Goodbye.")
        yield DoneEvent(message=ChatMessage(role="assistant", content="Goodbye."), ms=1)

    monkeypatch.setattr(fillers, "FAST_INTRO_DELAY", 0)
    monkeypatch.setattr(fillers, "fast_restatement", waiting_restatement)
    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.run_turn(conn.conversation, text="That's all, thanks.")
    assert calls == []
    assert [msg for msg in conn.ws.events if isinstance(msg, bytes)] == [b"Goodbye."]


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
    await conn.handle_text(json.dumps({"type": "text", "text": "Do you have flour in stock?"}))
    await asyncio.wait_for(started.wait(), timeout=2)
    await conn.handle_text(json.dumps({"type": "audio_start", "mime": "audio/webm"}))
    assert cancelled.is_set()
    assert [msg for msg in conn.ws.events if isinstance(msg, bytes)] == [b"I'll take a look."]
    assert conn.ws.events[-1]["type"] == "agent_audio_end"
    await conn.interrupt()


@pytest.mark.parametrize("call", ["0", "1", "2", "3"], indirect=True)
@pytest.mark.parametrize("orchestrator_enabled", ["0", "1"])
async def test_caller_form_prepares_first_greeting_before_transcription(call, monkeypatch, orchestrator_enabled):
    conn, tts = call
    monkeypatch.setenv("TEAM_ORCHESTRATOR", orchestrator_enabled)
    greeted = team_flags.fillers()
    greeting = "Hello, ma'am."
    call_message = CallerMessage.model_validate({
        "type": "caller", "clientId": "cli_0001", "contactName": "Nadine Sarrailh", "contactTitle": "madame",
    })
    sheet = CallContext(client_id="cli_0001", name="Maison Sarrailh", caller_contact="Nadine Sarrailh")

    async def load_sheet(erp, **kwargs):
        assert kwargs["contact_name"] == sheet.caller_contact
        return sheet

    class FirstUtterance:
        frames = [b"speech"]

        async def text(self):
            # Ordering guarantee, even when the provider's final transcript takes time.
            assert (greeting.encode() in conn.ws.events) is greeted
            return "Do you have flour in stock?"

        def cancel(self):
            pass

    async def agent(messages, **kwargs):
        assert kwargs["call_context"] is sheet
        reply = "Hello, ma'am Sarrailh, we have flour left." if len(messages) == 1 else "My pleasure."
        yield TextEvent(delta=reply)
        yield DoneEvent(message=ChatMessage(role="assistant", content=reply), ms=1)

    monkeypatch.setattr(voice_session.preload, "caller_context", load_sheet)
    monkeypatch.setattr(voice_session, "run_agent", agent)
    monkeypatch.setattr(orchestrator, "run_agent", agent)
    await conn.set_caller(call_message)
    assert (greeting in tts.phrases) is greeted
    assert conn.ws.events[-1]["type"] == "caller_ready"
    await conn.run_turn(conn.conversation, utterance=FirstUtterance())

    clips = [event for event in conn.ws.events if isinstance(event, bytes)]
    if greeted:
        assert clips[0] == greeting.encode()
        assert clips[-1] == b"We have flour left."
        first_wait = [fillers.FAST_INTRO] if team_flags.fillers_mode() == 2 else fillers.PHRASES["thinking"]
        assert clips[1].decode() in first_wait
    else:
        assert clips == [b"Hello, ma'am Sarrailh, we have flour left."]

    await conn.set_caller(call_message.model_copy(update={"resume": True}))
    await conn.run_turn(conn.conversation, text="Thanks.")
    assert conn.ws.events.count(greeting.encode()) == int(greeted)


@pytest.mark.parametrize("call", ["1"], indirect=True)
async def test_caller_form_without_title_uses_a_neutral_greeting(call, monkeypatch):
    conn, tts = call

    async def load_sheet(erp, **kwargs):
        return CallContext(client_id="cli_0001", name="Maison Sarrailh", caller_contact="Nadine Sarrailh")

    async def agent(messages, **kwargs):
        reply = "Hello Nadine, how can I help?"
        yield DoneEvent(message=ChatMessage(role="assistant", content=reply), ms=1)

    monkeypatch.setattr(voice_session.preload, "caller_context", load_sheet)
    monkeypatch.setattr(voice_session, "run_agent", agent)
    await conn.set_caller(CallerMessage(client_id="cli_0001"))
    assert "Hello." in tts.phrases
    await conn.run_turn(conn.conversation, text="Hello.")
    assert [event for event in conn.ws.events if isinstance(event, bytes)] == [b"Hello.", "How can I help?".encode()]


@pytest.mark.parametrize("call", ["3"], indirect=True)
async def test_combined_mode_plays_keyboard_while_restatement_is_prepared(call, monkeypatch):
    conn, _ = call
    for name in ("TEAM_ORCHESTRATOR", "TEAM_PRELOAD", "TEAM_ORDER_RULES", "TEAM_PRODUCT_INSIGHT", "TEAM_SALES_RULES"):
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(fillers, "FIRST_KEYBOARD_DELAY", 0)
    monkeypatch.setattr(fillers, "FAST_RESTATEMENT_DELAY", 0)
    keyboard = fillers.keyboard_click()
    heard = "I want 10 kg of flour or two sacks."
    recap = "You said: I want 10 kg of flour or two sacks."
    reply = "Which quantity would you prefer?"
    preparing = asyncio.Event()
    keyboard_played = asyncio.Event()
    recap_played = asyncio.Event()
    original_send = conn.ws.send_bytes

    async def restatement(transcript):
        assert transcript == heard
        preparing.set()
        await asyncio.wait_for(keyboard_played.wait(), timeout=1)
        return recap

    async def observe_audio(data):
        await original_send(data)
        if data == keyboard:
            assert preparing.is_set()
            keyboard_played.set()
        elif data == recap.encode():
            recap_played.set()

    async def agent(messages, **kwargs):
        yield ToolCallEvent(call=ToolCall(id="search", name="search", arguments={}))
        await asyncio.wait_for(recap_played.wait(), timeout=2)
        yield DoneEvent(message=ChatMessage(role="assistant", content=reply), ms=1)

    monkeypatch.setattr(fillers, "fast_restatement", restatement)
    monkeypatch.setattr(conn.ws, "send_bytes", observe_audio)
    monkeypatch.setattr(orchestrator, "run_agent", agent)
    await conn.run_turn(conn.conversation, text=heard)

    clips = [msg for msg in conn.ws.events if isinstance(msg, bytes)]
    assert clips[0].decode() in fillers.PHRASES["thinking"]
    assert clips[1:] == [keyboard, recap.encode(), reply.encode()]
    assert conn.ws.events[-1]["text"] == reply
