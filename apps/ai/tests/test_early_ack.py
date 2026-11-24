"""Mode 4 at the microphone: « je regarde » + typing start on the words heard so far, not 1.3 s later on the final
transcript (measured 24/11: the first sound came 1.33-1.86 s after the caller's last word)."""

import asyncio
from types import SimpleNamespace

from app.services import fillers


class FakeSpeaker:
    def __init__(self):
        self.tts = SimpleNamespace(name="elevenlabs")
        self.bank = SimpleNamespace(pick=lambda situation: SimpleNamespace(mime="audio/mpeg", data=b"ack"))
        self.played: list[tuple[float, bytes]] = []
        self.acknowledged = False
        self.transcript_ready = False
        self.waiting_task = None
        self.social_turn = False

    async def play_audio(self, mime, data, seconds=None):
        self.played.append((asyncio.get_running_loop().time(), data))


def _mode4(monkeypatch):
    monkeypatch.setenv("TEAM_FILLERS", "4")
    monkeypatch.setattr(fillers, "keep_typing", lambda speaker, delay=0.0: asyncio.sleep(0))


def test_acknowledges_on_the_partial_before_the_final_transcript(monkeypatch):
    _mode4(monkeypatch)

    async def scenario():
        speaker, utterance = FakeSpeaker(), SimpleNamespace(partial="Bonjour, vous avez encore du tourage")
        start = asyncio.get_running_loop().time()
        task = asyncio.create_task(fillers.early_acknowledgement(speaker, utterance))
        await asyncio.sleep(0.2)  # the final transcript is still 1 s away
        speaker.transcript_ready = True
        await task
        await fillers.on_turn_start(speaker, "Bonjour, vous avez encore du tourage AOP ?")  # final: nothing twice
        return speaker, start

    speaker, start = asyncio.run(scenario())
    assert [d for _, d in speaker.played] == [b"ack"] and speaker.played[0][0] - start < 0.1
    assert speaker.waiting_task is not None


def test_nothing_early_for_a_simple_reply_or_an_empty_partial(monkeypatch):
    _mode4(monkeypatch)

    async def scenario(partial):
        speaker = FakeSpeaker()
        task = asyncio.create_task(fillers.early_acknowledgement(speaker, SimpleNamespace(partial=partial)))
        await asyncio.sleep(0.15)
        speaker.transcript_ready = True
        await task
        return speaker

    for partial in ("", "Oui c'est bon", "Merci, au revoir"):
        s = asyncio.run(scenario(partial))
        assert not s.played and s.waiting_task is None  # final transcript within 0.4 s: nothing early


def test_typing_without_phrase_when_the_transcript_lags(monkeypatch):
    _mode4(monkeypatch)

    async def scenario():
        speaker = FakeSpeaker()
        task = asyncio.create_task(fillers.early_acknowledgement(speaker, SimpleNamespace(partial="C'est bon, validé")))
        await asyncio.sleep(0.6)  # the final transcript is late (1.2-1.6 s at the mic)
        speaker.transcript_ready = True
        await task
        return speaker

    s = asyncio.run(scenario())
    assert not s.played and s.waiting_task is not None  # typing, no « je regarde » for a simple reply


def test_off_outside_mode_4(monkeypatch):
    monkeypatch.setenv("TEAM_FILLERS", "1")

    async def scenario():
        speaker = FakeSpeaker()
        await fillers.early_acknowledgement(speaker, SimpleNamespace(partial="vous avez encore du tourage"))
        return speaker

    assert not asyncio.run(scenario()).played
