"""Youssef · natural voice (24/11): style rules in the voice prompt, varied waiting phrases, varied openings, nudge."""

import json

from app.agent.listening import STYLE_RULES, listening_section
from app.clients.base import TTSResult
from app.services import fillers, voice_session
from app.services.voice_reply import vary_opening


def test_style_rules_only_on_the_phone():
    assert STYLE_RULES in listening_section("voice") and listening_section("chat") == ""
    for must in ("sous tes yeux", "Varie", "pressé", "plus de 3 options", "robot", "ne les recopie pas"):
        assert must in STYLE_RULES


def test_waiting_phrases_never_repeat_back_to_back_and_all_are_used():
    bank = fillers.FillerBank()
    bank.audio["thinking"] = [fillers.CachedAudio("audio/mpeg", p.encode()) for p in fillers.PHRASES["thinking"]]
    picks = [bank.pick("thinking").data for _ in range(40)]
    assert all(a != b for a, b in zip(picks, picks[1:]))
    n = len(fillers.PHRASES["thinking"])
    assert len(set(picks[:n])) == n


def test_the_same_acknowledgement_never_opens_two_replies_in_a_row():
    assert vary_opening("Parfait, et je vous ajoute la levure.", "Parfait, c'est noté.") == "Et je vous ajoute la levure."
    assert vary_opening("Très bien, c'est noté.", "Parfait, c'est noté.") == "Très bien, c'est noté."
    assert vary_opening("Parfait.", "Parfait, c'est noté.") == "Parfait."  # nothing left to say: keep it
    assert vary_opening("D'accord, je note.", None) == "D'accord, je note."


class Sock:
    def __init__(self):
        self.events = []

    async def send_text(self, m):
        self.events.append(json.loads(m))

    async def send_bytes(self, b):
        self.events.append(b)


class TTS:
    name = "test"

    async def synthesize(self, text, voice=None):
        async def chunks():
            yield text.encode()

        return TTSResult("audio/mpeg", chunks())


async def test_nudge_is_varied_spoken_and_kept_out_of_the_history(monkeypatch):
    import asyncio

    monkeypatch.setattr(voice_session, "get_tts_client", lambda: TTS())
    conn = voice_session.VoiceConnection(Sock())
    conn.conversation = voice_session.Conversation(id="t")
    said = []
    for _ in range(3):
        await conn.nudge()
        said.append([e for e in conn.ws.events if isinstance(e, dict) and e.get("type") == "nudge_said"][-1]["text"])
    assert len(set(said)) == 3 and all(s in fillers.NUDGES for s in said)
    assert any(isinstance(e, bytes) for e in conn.ws.events)  # spoken
    assert conn.conversation.history == []
    conn.turn = asyncio.get_running_loop().create_future()  # the agent is working: no nudge
    n = len(conn.ws.events)
    await conn.nudge()
    assert len(conn.ws.events) == n
