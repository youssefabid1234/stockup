"""Youssef · the caller chosen in the form is never forgotten during the call (voice session level)."""

import pytest

from app.agent import call_context as cc_mod
from app.agent.call_context import CallContext
from app.schemas import CallerMessage, ChatMessage
from app.services import voice_session
from app.services.voice_session import Conversation, VoiceConnection


class FakeWs:
    def __init__(self):
        self.sent = []


@pytest.fixture
def conn(monkeypatch):
    async def caller_context(erp, **kw):
        return CallContext(client_id=kw.get("client_id") or "", name="Maison Sarrailh", caller_contact=kw.get("contact_name"))

    monkeypatch.setattr(cc_mod, "caller_context", caller_context)
    monkeypatch.delenv("TEAM_PRELOAD", raising=False)  # switch OFF: the explicit caller must still reach the agent
    c = VoiceConnection(FakeWs())
    sent = []

    async def send(msg):
        sent.append(msg)

    c.send = send
    c.sent = sent
    c.conversation = Conversation(id="s1", history=[ChatMessage(role="user", content="avant")])
    return c


async def test_new_call_sets_the_sheet_even_with_preload_off_and_clears_history(conn):
    await conn.set_caller(CallerMessage(client_id="cli_0001", contact_name="Nadine"))
    assert conn.conversation.call_context.name == "Maison Sarrailh"
    assert conn.conversation.call_context.caller_contact == "Nadine"
    assert conn.conversation.history == []
    ready = conn.sent[-1]
    assert ready.used_by_agent and not ready.resume


async def test_resume_after_reconnect_keeps_the_conversation(conn):
    await conn.set_caller(CallerMessage(client_id="cli_0001", contact_name="Nadine", resume=True))
    assert conn.conversation.call_context is not None
    assert [m.content for m in conn.conversation.history] == ["avant"]  # not wiped
    assert conn.sent[-1].resume


async def test_cached_sheet_is_copied_per_call(monkeypatch):
    cc_mod.clear_cache()
    base = CallContext(client_id="cli_0001", name="Maison Sarrailh")
    cc_mod._cache["cli_0001"] = (float("inf"), base)
    guy = await cc_mod.caller_context(None, client_id="cli_0001", contact_name="Guy")
    nadine = await cc_mod.caller_context(None, client_id="cli_0001", contact_name="Nadine")
    assert (guy.caller_contact, nadine.caller_contact, base.caller_contact) == ("Guy", "Nadine", None)
    cc_mod.clear_cache()


def test_voice_session_uses_the_module_function():
    # set_caller must go through call_context.caller_context (patched above), not a stale import
    assert voice_session.preload is cc_mod
