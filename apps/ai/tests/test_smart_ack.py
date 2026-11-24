"""Youssef · the first words follow the request (24/11): intent → its own neutral phrases, never a promise."""

import pytest

from app.services import fillers


@pytest.mark.parametrize("said, intent", [
    ("Vous pourriez me faire 10 % sur l'ensemble ? Votre concurrent fait moins cher.", "discount"),
    ("Il manquait deux sacs dans ma livraison.", "complaint"),
    ("Confirmez-moi la commande.", "readback"),
    ("Vous pouvez me relire la commande ?", "readback"),
    ("Combien ça fait en tout ?", "total"),
    ("Comme d'habitude pour mercredi.", "usual"),
    ("Non, mettez-en 12.", "change"),
    ("C'est combien la levure ?", "price"),
    ("Vous avez du tourage AOP ?", "stock"),
    ("Il me faut 10 sacs de tradi.", "order"),
    ("Pour jeudi.", "delivery"),
    ("Oui.", None),
    ("Vous êtes un robot ?", None),
])
def test_intent_of(said, intent):
    assert fillers.intent_of(said) == intent


def test_no_phrase_sounds_like_a_yes():
    every = [p for ps in fillers.ACK_BY_INTENT.values() for p in ps] + fillers.ACK_PHRASES
    assert not [p for p in every if p.lower().startswith(("parfait", "ça marche", "c'est noté", "oui"))]
    assert all(len(p) <= 45 for p in every)  # short: under a second and a half


async def test_the_phrase_played_matches_the_intent(monkeypatch):
    monkeypatch.setenv("TEAM_FILLERS", "4")
    bank = fillers.FillerBank()
    for k, phrases in fillers.ACK_BY_INTENT.items():
        bank.audio[f"ack:{k}"] = [fillers.CachedAudio("audio/mpeg", p.encode(), p) for p in phrases]
    bank.audio["ack"] = [fillers.CachedAudio("audio/mpeg", p.encode(), p) for p in fillers.ACK_PHRASES]

    class Speaker:
        def __init__(self, intent):
            self.bank, self.intent, self.played, self.acknowledged = bank, intent, [], False

        async def play_audio(self, mime, data, seconds=None):
            self.played.append(data.decode())

    for intent in ("discount", "readback", "price"):
        sp = Speaker(intent)
        assert await fillers.play_waiting_line(sp)
        assert sp.played[0] in fillers.ACK_BY_INTENT[intent]
    sp = Speaker(None)
    await fillers.play_waiting_line(sp)
    assert sp.played[0] in fillers.ACK_PHRASES


async def test_jev_decides_when_no_keyword_and_never_blocks(monkeypatch):
    import asyncio
    import app.clients as clients
    from types import SimpleNamespace

    class Jev:
        async def choose(self, state, q, options):
            return SimpleNamespace(choice="complaint", confidence=0.9)

    monkeypatch.setattr(clients, "get_jev_client", lambda: Jev())
    assert await fillers.choose_intent("Bon, là, ça ne va pas du tout avec vous.") == "complaint"

    class SlowJev:
        async def choose(self, state, q, options):
            await asyncio.sleep(2)

    monkeypatch.setattr(clients, "get_jev_client", lambda: SlowJev())
    loop = asyncio.get_running_loop()
    t0 = loop.time()
    assert await fillers.choose_intent("Bon, là, ça ne va pas du tout avec vous.") is None
    assert loop.time() - t0 < fillers.JEV_TIMEOUT + 0.1


async def test_greeting_by_first_name_when_no_civility(monkeypatch):
    from app.schemas import CallerMessage
    from app.services import voice_session

    monkeypatch.setenv("TEAM_FILLERS", "4")

    async def sheet(erp, **kw):
        return None

    monkeypatch.setattr(voice_session.preload, "caller_context", sheet)

    class Sock:
        async def send_text(self, m):
            pass

        async def send_bytes(self, b):
            pass

    conn = voice_session.VoiceConnection(Sock())
    conn.conversation = voice_session.Conversation(id="g")
    conn.prepare_greeting = lambda g: _noop()
    conn.play_opening = lambda *a, **k: _noop()
    await conn.set_caller(CallerMessage(client_id="cli_0089", contact_name="Damien Guérin"))
    assert conn.conversation.opening_greeting == "Bonjour Damien, que puis-je faire pour vous ?"


async def _noop():
    return None
