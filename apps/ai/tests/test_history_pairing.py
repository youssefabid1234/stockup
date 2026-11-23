"""
Tool-call / tool-result pairing across everything that builds or replays a conversation:
the agent loop, the history the browser rebuilds from /chat events (TurnRecorder, ported below),
sanitize_history() (POST /chat + voice history), trim(), voice barge-in, and the provider conversions.

A broken pairing is a provider 400 ("unexpected tool_use_id found in tool_result blocks…") that then
fails every following turn of the conversation.
"""

import asyncio
import json

import pytest

from app.agent import loop as agent_loop
from app.agent import run_agent, sanitize_history
from app.agent.sanitize import INTERRUPTED
from app.clients import LLMClient, LLMRequest, LLMText, LLMToolCall
from app.clients.anthropic import to_anthropic_messages
from app.clients.gemini import to_gemini_contents
from app.clients.openai import to_openai_message
from app.schemas import ChatMessage, DoneEvent, ErrorEvent, TextEvent, ToolCall, ToolCallEvent, ToolResultEvent
from app.services import voice_session
from app.services.voice_session import trim
from app.tools.registry import Tool, ToolArgs

# ── helpers ──


class TurnRecorder:
    """Python port of apps/web/src/features/assistant/turn-recorder.ts (keep in sync)."""

    def __init__(self):
        self.messages: list[ChatMessage] = []
        self.text, self.calls, self.in_results = "", [], False

    def push(self, e) -> None:
        if isinstance(e, TextEvent):
            self.in_results = False
            self.text += e.delta
        elif isinstance(e, ToolCallEvent):
            self.in_results = False  # a call after results = a new model step
            self.calls.append(e.call)
        elif isinstance(e, ToolResultEvent):
            if not self.in_results:
                self.messages.append(ChatMessage(role="assistant", content=self.text, tool_calls=self.calls))
                self.text, self.calls, self.in_results = "", [], True
            self.messages.append(ChatMessage(role="tool", tool_call_id=e.call_id, name=e.name, content=json.dumps(e.result)))
        elif isinstance(e, DoneEvent):
            self._close_open_calls()
            self.messages.append(e.message)
            self.text, self.calls, self.in_results = "", [], False

    def finish(self) -> list[ChatMessage]:
        self._close_open_calls()
        last = self.messages[-1] if self.messages else None
        if not last or last.role != "assistant" or last.tool_calls:
            self.messages.append(ChatMessage(role="assistant", content=self.text.strip() or "(réponse interrompue)"))
        return self.messages

    def _close_open_calls(self) -> None:
        i = len(self.messages) - 1
        while i >= 0 and self.messages[i].role == "tool":
            i -= 1
        if i < 0 or self.messages[i].role != "assistant" or not self.messages[i].tool_calls:
            return
        answered = {m.tool_call_id for m in self.messages[i + 1 :]}
        for c in self.messages[i].tool_calls:
            if c.id not in answered:
                self.messages.append(ChatMessage(role="tool", tool_call_id=c.id, name=c.name, content=INTERRUPTED))


def assert_paired(messages: list[ChatMessage]) -> None:
    """Provider rule: each tool block answers exactly the calls of the assistant message right before it."""
    for i, m in enumerate(messages):
        if m.role == "tool":
            j = i
            while j >= 0 and messages[j].role == "tool":
                j -= 1
            owner = messages[j] if j >= 0 else None
            assert owner and owner.role == "assistant" and any(c.id == m.tool_call_id for c in owner.tool_calls or []), f"orphan result at {i}"
        if m.role == "assistant" and m.tool_calls:
            block = []
            k = i + 1
            while k < len(messages) and messages[k].role == "tool":
                block.append(messages[k].tool_call_id)
                k += 1
            assert sorted(block) == sorted(c.id for c in m.tool_calls), f"calls of message {i} not all answered: {block}"


def assert_anthropic_valid(messages: list[ChatMessage]) -> None:
    """The checks behind Anthropic's 400s, on the converted body."""
    out = to_anthropic_messages(messages)
    for k, msg in enumerate(out):
        for b in msg["content"]:
            assert b.get("type") != "text" or b["text"].strip(), f"blank text block in message {k}"
        results = [b["tool_use_id"] for b in msg["content"] if b["type"] == "tool_result"]
        if results:
            assert msg["role"] == "user" and msg["content"][0]["type"] == "tool_result"
            prev = out[k - 1] if k else None
            uses = [b["id"] for b in prev["content"] if b["type"] == "tool_use"] if prev and prev["role"] == "assistant" else []
            assert sorted(results) == sorted(uses), f"message {k}: results {results} vs tool_use {uses}"
        uses = [b["id"] for b in msg["content"] if b["type"] == "tool_use"]
        if uses:
            nxt = out[k + 1] if k + 1 < len(out) else None
            got = [b["tool_use_id"] for b in nxt["content"] if b["type"] == "tool_result"] if nxt else []
            assert sorted(got) == sorted(uses), f"tool_use {uses} without results"


class ScriptedLLM(LLMClient):
    """Plays one list of events per model call."""

    provider, model = "scripted", "scripted"

    def __init__(self, steps):
        self.steps, self.requests = list(steps), []

    async def stream(self, request: LLMRequest):
        self.requests.append(list(request.messages))
        for ev in self.steps.pop(0) if self.steps else [LLMText("Fin.")]:
            if ev == "SLEEP":
                await asyncio.sleep(10)
            yield ev


def call(id: str, name: str = "lookup") -> LLMToolCall:
    return LLMToolCall(ToolCall(id=id, name=name, arguments={}))


async def _lookup(ctx):
    return {"ok": True}


async def _fail(ctx):
    raise RuntimeError("boom")


async def _slow(ctx):
    await asyncio.sleep(10)


TOOLS = [
    Tool("lookup", "Lookup", ToolArgs, _lookup),
    Tool("fail", "Fails", ToolArgs, _fail),
    Tool("slow", "Slow", ToolArgs, _slow),
]


@pytest.fixture(autouse=True)
def no_erp_prompt(monkeypatch):
    async def prompt(mode, actor_name=None):
        return "SYS"

    monkeypatch.setattr(agent_loop, "build_system_prompt", prompt)


async def run(steps, history=None, max_steps=None):
    """Run one turn; return (server messages, browser-rebuilt messages, events)."""
    server = [*(history or []), ChatMessage(role="user", content="go")]
    llm = ScriptedLLM(steps)
    rec, events = TurnRecorder(), []
    async for ev in run_agent(server, llm=llm, tools=TOOLS, max_steps=max_steps):
        rec.push(ev)
        events.append(ev)
    browser = [*(history or []), ChatMessage(role="user", content="go"), *rec.finish()]
    return server, browser, events, llm


# ── the agent loop + the browser's rebuild ──


SCENARIOS = {
    "two_chained_rounds_no_text": [[call("a")], [call("b")], [LLMText("Voilà.")]],
    "parallel_then_second_round": [[call("a"), call("b")], [call("c")], [LLMText("OK.")]],
    "text_and_calls_same_step": [[LLMText("Je regarde."), call("a")], [LLMText("Encore "), call("b"), call("c")], [LLMText("Fait.")]],
    "tool_error_result": [[call("a", "fail")], [call("b", "unknown_tool")], [LLMText("Erreur.")]],
    "whitespace_text_before_calls": [[LLMText("\n\n"), call("a")], [LLMText("OK")]],
}


@pytest.mark.parametrize("name", SCENARIOS)
async def test_server_and_browser_histories_are_paired(name):
    server, browser, _, _ = await run(SCENARIOS[name])
    for msgs in (server, browser):
        assert_paired(msgs)
        assert_anthropic_valid(msgs)
    # the browser rebuilt the same structure the server holds
    assert [(m.role, [c.id for c in m.tool_calls or []], m.tool_call_id) for m in browser] == [
        (m.role, [c.id for c in m.tool_calls or []], m.tool_call_id) for m in server
    ]
    # and a second turn on top of it is still valid
    server2, browser2, _, _ = await run([[call("z")], [LLMText("Re.")]], history=browser)
    assert_paired(browser2)
    assert_anthropic_valid(browser2)


async def test_max_steps_reached_mid_tools():
    server, browser, events, _ = await run([[call("a")], [call("b")], [call("c")]], max_steps=2)
    assert isinstance(events[-1], DoneEvent) and events[-1].message.content == agent_loop.GIVE_UP
    for msgs in (server, browser):
        assert_paired(msgs)
        assert_anthropic_valid(msgs)


async def test_error_after_some_tool_results():
    class Boom(ScriptedLLM):
        async def stream(self, request):
            if len(self.requests) == 2:
                raise RuntimeError("provider down")
            async for ev in super().stream(request):
                yield ev

    server = [ChatMessage(role="user", content="go")]
    rec = TurnRecorder()
    async for ev in run_agent(server, llm=Boom([[call("a")], [call("b")]]), tools=TOOLS):
        rec.push(ev)
    assert server[-1].role == "tool"  # the loop leaves the done rounds, paired
    browser = [ChatMessage(role="user", content="go"), *rec.finish()]
    assert browser[-1].content == "(réponse interrompue)"
    assert_paired(browser)
    assert_anthropic_valid([*browser, ChatMessage(role="user", content="encore")])


async def test_browser_cut_between_parallel_results():
    """Stop / network cut after the first of two parallel results: the missing one is synthesized."""
    _, _, events, _ = await run([[call("a"), call("b")], [LLMText("OK")]])
    rec = TurnRecorder()
    for ev in events[: events.index(next(e for e in events if isinstance(e, ToolResultEvent))) + 1]:
        rec.push(ev)
    msgs = [ChatMessage(role="user", content="go"), *rec.finish()]
    assert_paired(msgs)
    assert next(m for m in msgs if m.tool_call_id == "b").content == INTERRUPTED


# ── sanitize_history ──


U = ChatMessage(role="user", content="go")


def A(content="", *ids):
    return ChatMessage(role="assistant", content=content, tool_calls=[ToolCall(id=i, name="lookup") for i in ids] or None)


def R(id):
    return ChatMessage(role="tool", tool_call_id=id, name="lookup", content="{}")


def test_sanitize_keeps_a_valid_history_unchanged():
    msgs = [U, A("", "a", "b"), R("a"), R("b"), A("", "c"), R("c"), A("ok"), U]
    assert sanitize_history(msgs) == msgs


def test_sanitize_old_turnrecorder_bug_shape():
    """The pre-fix browser history: round 2's result glued under round 1's assistant, round 2's call lost."""
    bad = [U, A("", "a"), R("a"), R("b"), A("Voilà."), U]
    fixed = sanitize_history(bad)
    assert fixed == [U, A("", "a"), R("a"), A("Voilà."), U]
    assert_anthropic_valid(fixed)


def test_sanitize_missing_and_dangling_results_get_interrupted():
    fixed = sanitize_history([U, A("", "a", "b"), R("b"), U, A("je crée", "c")])
    assert [(m.role, m.tool_call_id) for m in fixed] == [("user", None), ("assistant", None), ("tool", "a"), ("tool", "b"), ("user", None), ("assistant", None), ("tool", "c")]
    assert fixed[2].content == INTERRUPTED and fixed[6].content == INTERRUPTED and fixed[6].name == "lookup"
    assert_paired(fixed)


def test_sanitize_drops_orphans_duplicates_empties_system_and_leading_non_user():
    msgs = [
        R("x"),
        A("bonjour"),
        ChatMessage(role="system", content="sys"),
        U,
        R("y"),  # orphan after a user message
        A("", "a", "a"),  # duplicated id
        R("a"),
        R("a"),  # duplicated result
        R("zz"),  # not one of this step's calls
        A("   "),  # blank assistant
        ChatMessage(role="assistant", content="", tool_calls=[]),  # empty tool_calls
        ChatMessage(role="user", content="  "),
        U,
    ]
    fixed = sanitize_history(msgs)
    assert [(m.role, m.tool_call_id) for m in fixed] == [("user", None), ("assistant", None), ("tool", "a"), ("user", None)]
    assert [c.id for c in fixed[1].tool_calls] == ["a"]
    assert_anthropic_valid(fixed)


def test_sanitize_blank_text_with_calls_and_result_name_filled():
    fixed = sanitize_history([U, A("  \n", "a"), ChatMessage(role="tool", tool_call_id="a", content="{}")])
    assert fixed[1].content == "" and fixed[2].name == "lookup"
    assert to_gemini_contents(fixed)[-1]["parts"][0]["functionResponse"]["name"] == "lookup"


def test_every_provider_conversion_after_sanitize():
    fixed = sanitize_history([U, A("Je regarde.", "a", "b"), R("a"), R("zz"), A("", "c")])
    assert_anthropic_valid(fixed)
    oa = [to_openai_message(m) for m in fixed]
    ids = [tc["id"] for m in oa if m.get("tool_calls") for tc in m["tool_calls"]]
    assert sorted(m["tool_call_id"] for m in oa if m["role"] == "tool") == sorted(ids)
    gem = to_gemini_contents(fixed)
    calls = sum("functionCall" in p for c in gem for p in c["parts"])
    responses = sum("functionResponse" in p for c in gem for p in c["parts"])
    assert calls == responses == 3


def test_anthropic_no_blank_text_blocks():
    out = to_anthropic_messages([U, A("\n\n", "a"), R("a"), A("  "), ChatMessage(role="user", content=" ")])
    assert [b["type"] for b in out[1]["content"]] == ["tool_use"]
    assert len(out) == 3  # blank assistant / user messages are skipped


# ── trim + voice ──


def test_trim_never_splits_a_tool_round_and_starts_on_user():
    history: list[ChatMessage] = []
    for n in range(12):  # 12 turns × 4-5 messages
        history += [ChatMessage(role="user", content=f"q{n}"), A("", f"a{n}", f"b{n}"), R(f"a{n}"), R(f"b{n}"), A(f"r{n}")]
    for cut in range(len(history) - 5, len(history) + 1):
        trimmed = trim(history[:cut] + ([] if cut % 2 else [ChatMessage(role="user", content="x")]))
        assert trimmed[0].role == "user"
        assert_paired(trimmed)
        assert_anthropic_valid(trimmed)
    assert len(trim(history)) <= 40


def test_trim_closes_a_dangling_call():
    assert_paired(trim([U, A("", "a")]))


class FakeWS:
    def __init__(self):
        self.sent = []

    async def send_text(self, text):
        self.sent.append(json.loads(text))

    async def send_bytes(self, data):
        pass


def voice_session_with(monkeypatch, steps, tts_sleep=False):
    from app.clients.mock_speech import MockTTS

    llm = ScriptedLLM(steps)
    monkeypatch.setattr(voice_session, "get_llm_client", lambda: llm)
    monkeypatch.setattr(voice_session, "all_tools", lambda: TOOLS)
    if tts_sleep:
        class SlowTTS(MockTTS):
            async def synthesize(self, text, voice=None):
                await asyncio.sleep(10)

        monkeypatch.setattr(voice_session, "get_tts_client", lambda: SlowTTS())
    else:
        monkeypatch.setattr(voice_session, "get_tts_client", lambda: MockTTS())
    session = voice_session.VoiceConnection(FakeWS())
    conv = voice_session.Conversation(id="t")
    return session, conv, llm


async def _barge_in(session, conv, text, after=0.05):
    task = asyncio.create_task(session.run_turn(conv, text=text))
    await asyncio.sleep(after)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


async def test_voice_barge_in_mid_tool_keeps_done_rounds_and_stays_valid(monkeypatch):
    session, conv, _ = voice_session_with(monkeypatch, [[call("a")], [LLMText("Je crée."), call("s", "slow")]])
    await _barge_in(session, conv, "crée la commande")
    h = conv.history
    assert [m.role for m in h] == ["user", "assistant", "tool", "assistant", "tool"]
    assert h[2].tool_call_id == "a" and h[2].content != INTERRUPTED  # the round that ran stays known
    assert h[4].tool_call_id == "s" and h[4].content == INTERRUPTED
    assert_paired(h)
    assert_anthropic_valid([*h, ChatMessage(role="user", content="et alors ?")])


async def test_voice_barge_in_mid_text_after_tools(monkeypatch):
    session, conv, _ = voice_session_with(monkeypatch, [[call("a")], [LLMText("Voici le"), "SLEEP"]])
    await _barge_in(session, conv, "liste")
    assert [m.role for m in conv.history] == ["user", "assistant", "tool", "assistant"]
    assert conv.history[-1].content == "Voici le …"
    assert_paired(conv.history)


async def test_voice_barge_in_during_last_audio_does_not_duplicate_the_turn(monkeypatch):
    session, conv, _ = voice_session_with(monkeypatch, [[LLMText("Bonjour. Je suis là. ")]], tts_sleep=True)
    await _barge_in(session, conv, "allo", after=0.1)
    assert [(m.role, m.content) for m in conv.history] == [("user", "allo"), ("assistant", "Bonjour. Je suis là. ")]


async def test_voice_error_mid_turn_then_next_turn_valid(monkeypatch):
    class Boom(ScriptedLLM):
        async def stream(self, request):
            if len(self.requests) == 1:
                self.requests.append(None)
                raise RuntimeError("provider down")
            async for ev in super().stream(request):
                yield ev

    llm = Boom([[call("a")], [LLMText("OK")]])
    session, conv, _ = voice_session_with(monkeypatch, [])
    monkeypatch.setattr(voice_session, "get_llm_client", lambda: llm)
    await session.run_turn(conv, text="un")
    await session.run_turn(conv, text="deux")
    assert any(m.get("type") == "error" for m in session.ws.sent)
    assert_paired(conv.history)
    assert_anthropic_valid(conv.history)
