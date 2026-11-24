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


# ── 24/11, second pass: one question per reply, varied validation question ──

from app.services.voice_reply import one_question, vary_closing  # noqa: E402


def test_only_the_last_question_stays_a_question():
    raw = "Bonjour. Je vous mets de la crème liquide, celle à trente-cinq pour cent ? Vous en voulez combien de litres ?"
    assert one_question(raw) == "Bonjour. Je vous mets de la crème liquide, celle à trente-cinq pour cent. Vous en voulez combien de litres ?"
    assert one_question("Vous en voulez combien ?") == "Vous en voulez combien ?"
    assert one_question("C'est noté. Le total fait 95 euros.") == "C'est noté. Le total fait 95 euros."


def test_a_validation_question_is_never_asked_twice_in_a_call():
    used: list[str] = []
    first = vary_closing("Cinq sacs de T65 pour mercredi. On part là-dessus ?", used)
    second = vary_closing("C'est ajouté, dix pains de levure. On part là-dessus ?", used)
    third = vary_closing("Le total fait 157 euros. On part là-dessus ?", used)
    closings = [s.rsplit(". ", 1)[-1] for s in (first, second, third)]
    assert closings[0] == "On part là-dessus ?" and len(set(closings)) == 3
    assert vary_closing("Vous en voulez combien ?", used) == "Vous en voulez combien ?"  # not a validation question


def test_the_doubtful_word_rule_asks_explicitly():
    assert "ne le devine pas" in STYLE_RULES and "quelle farine" in STYLE_RULES


# ── French voice (24/11): what the TTS reads, fallback voice ──

from app.clients.french_speech import tts_text  # noqa: E402


def test_codes_and_symbols_are_read_as_words():
    assert tts_text("2 cartons de T55 à 8,46 € HT, 82 % AOP.") == "2 cartons de T 55 à 8 euros 46 hors taxes, 82 pour cent A O P."
    assert tts_text("10 kg, 500 g et 6 L.") == "10 kilos, 500 grammes et 6 litres."
    assert tts_text("Carton 10 × 1 kg, commande n° 12.") == "Carton 10 fois 1 kilos, commande numéro 12."
    assert tts_text("Bonjour Nadine, je vous écoute.") == "Bonjour Nadine, je vous écoute."  # plain French untouched
    assert tts_text("le prix est de 18,50 euros.") == "le prix est de 18 euros 50."


async def test_a_voice_missing_from_the_key_falls_back_to_a_premade_one():
    from app.clients.elevenlabs import ElevenLabsTTS

    tts = ElevenLabsTTS("k", voice="not-in-this-library")
    asked = []

    async def stream(text, voice):
        asked.append(voice)
        if voice != ElevenLabsTTS.FALLBACK_VOICE:
            raise RuntimeError("voice_not_found")
        return None

    tts._stream = stream
    import app.clients.elevenlabs as el

    el.body_chunks = lambda res: iter(())
    await tts.synthesize("Bonjour")
    await tts.synthesize("Encore")
    assert asked == ["not-in-this-library", ElevenLabsTTS.FALLBACK_VOICE, ElevenLabsTTS.FALLBACK_VOICE]
