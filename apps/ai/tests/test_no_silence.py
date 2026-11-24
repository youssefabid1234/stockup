"""Mode 4 · « zéro silence » (TEAM_FILLERS=4): the agent opens the call, acknowledges at once, types until the answer."""

import asyncio

import pytest

from app.services import fillers
from app.services.voice_session import Speaker


class FakeTTS:
    name = "elevenlabs"

    async def synthesize(self, text, voice=None):  # pragma: no cover - not used: clips come from the bank
        raise AssertionError("no live synthesis expected")


def speaker_with_bank(sent_bytes: list, events: list | None = None) -> Speaker:
    async def send(msg):
        if events is not None:
            events.append(type(msg).__name__)

    async def send_bytes(data):
        sent_bytes.append(data)

    bank = fillers.FillerBank()
    bank.audio["ack"] = [fillers.CachedAudio("audio/mpeg", b"\xff" * 16000)]  # 1 s at 128 kbps
    return Speaker(FakeTTS(), send, send_bytes, bank)


@pytest.fixture
def mode4(monkeypatch):
    monkeypatch.setenv("TEAM_FILLERS", "4")


def test_typing_clips_are_short_and_varied():
    clips = {fillers.typing_clip(i)[0] for i in range(6)}
    assert len(clips) == 6  # six different rhythms, not one loop
    data, seconds = fillers.typing_clip(0)
    assert data and seconds == fillers.TYPING_SECONDS <= 0.5


def test_mp3_seconds():
    assert fillers.mp3_seconds(b"\x00" * 16000) == pytest.approx(1.0)


async def test_request_gets_an_acknowledgement_then_typing_without_gap(mode4):
    sent: list[bytes] = []
    sp = speaker_with_bank(sent)
    await fillers.on_turn_start(sp, "Il me faudrait dix sacs de tradi pour jeudi.")
    assert sp.acknowledged and sent[0] == b"\xff" * 16000  # « D'accord, je regarde ça » at once
    await asyncio.sleep(1.4)  # the ack plays 1 s, then typing must follow
    await sp.stop_waiting()
    typing = sent[1:]
    assert len(typing) >= 1  # typing started before the ack ran out
    loop = asyncio.get_running_loop()
    assert sp.audio_until - loop.time() <= fillers.TYPING_SECONDS + fillers.TYPING_LEAD + 0.05  # no backlog


async def test_social_turn_gets_no_phrase_only_late_typing(mode4):
    sent: list[bytes] = []
    sp = speaker_with_bank(sent)
    await fillers.on_turn_start(sp, "Merci, au revoir.")
    assert not sp.acknowledged and sent == []
    await asyncio.sleep(fillers.SOCIAL_TYPING_DELAY + 0.1)
    await sp.stop_waiting()
    assert sent  # typing only, if the answer takes a moment


async def test_typing_stops_when_cancelled(mode4):
    sent: list[bytes] = []
    sp = speaker_with_bank(sent)
    await fillers.on_turn_start(sp, "C'est combien le sac ?")
    await asyncio.sleep(0.2)
    await sp.stop_waiting()
    count = len(sent)
    await asyncio.sleep(0.8)
    assert len(sent) == count


async def test_other_modes_untouched(monkeypatch):
    monkeypatch.setenv("TEAM_FILLERS", "1")
    sent: list[bytes] = []
    sp = speaker_with_bank(sent)
    await fillers.on_turn_start(sp, "Merci, au revoir.")
    assert sp.waiting_task is None and sent == []


async def test_agent_opens_the_call(mode4):
    from app.services.voice_session import Conversation, VoiceConnection

    events: list[str] = []
    sent: list[bytes] = []
    conn = VoiceConnection.__new__(VoiceConnection)
    conn.bank = fillers.FillerBank()
    conn.greetings = {fillers.OPENING_LINES["madame"]: fillers.CachedAudio("audio/mpeg", b"\xff" * 1000)}

    async def send(msg):
        events.append(type(msg).__name__)

    async def send_bytes(data):
        sent.append(data)

    conn.send, conn.send_bytes = send, send_bytes
    conv = Conversation(id="c1", opening_greeting=fillers.OPENING_LINES["madame"])
    await conn.open_the_call(conv)
    assert sent == [b"\xff" * 1000]
    assert events == ["AgentAudioStartMessage", "AgentAudioEndMessage"]
    assert conv.agent_opened and conv.opening_greeting is None


def test_opening_lines_ask_what_the_caller_wants():
    assert fillers.OPENING_LINES["madame"] == "Bonjour Madame, que puis-je faire pour vous ?"
    assert all("que puis-je faire pour vous" in line for line in fillers.OPENING_LINES.values())
