"""TEAM_FAST_REPLY: a clean order / confirmation result is said as is (no 2nd model call); anything unusual → the model."""

from types import SimpleNamespace

from app.agent import fast_reply

CLEAN = {"written": True, "orderId": "ord_1", "canConfirm": True, "totalHt": 189.0, "alerts": [], "askFirst": [],
         "duplicateDrafts": [], "sameDayOrders": [], "franco": None,
         "readback": "10 sacs de Farine de blé T55 tradition française ; livraison jeudi 26 novembre"}


def run(name, result, ok=True, mode="voice"):
    return fast_reply.compose(mode, [SimpleNamespace(name=name)], [SimpleNamespace(name=name, ok=ok, result=result)])


def test_off_by_default():
    assert run("place_order", CLEAN) is None


def test_clean_order_is_read_back_directly(monkeypatch):
    monkeypatch.setenv("TEAM_FAST_REPLY", "1")
    said = run("place_order", CLEAN)
    assert any(said.startswith(o) for o in fast_reply.OPENERS)
    assert "10 sacs de farine de blé T55 tradition française, et vous serez livrés jeudi 26 novembre." in said
    assert "189 euros hors taxes" in said and any(said.endswith(a) for a in fast_reply.ASKS)
    assert run("place_order", CLEAN) == said  # the same order: the same words (no flicker on a replay)
    franco = {**CLEAN, "totalHt": 37.8, "franco": "la commande fait 38 euros hors taxes : en dessous de 150 euros, il y a 12 euros de livraison"}
    assert "Ça fait 37 euros 80 hors taxes, donc bon, il y aura 12 euros de frais de livraison" in run("place_order", franco)
    assert run("place_order", franco).endswith("Je vous la valide quand même ?")


def test_anything_unusual_goes_back_to_the_model(monkeypatch):
    monkeypatch.setenv("TEAM_FAST_REPLY", "1")
    for extra in ({"alerts": ["compte bloqué"]}, {"askFirst": [{"productId": "p"}]}, {"sameDayOrders": [{"id": "o"}]},
                  {"duplicateDrafts": [{"id": "o"}]}, {"canConfirm": False}, {"written": False, "next": "Quel jour ?"}):
        assert run("place_order", {**CLEAN, **extra}) is None, extra
    assert run("place_order", CLEAN, ok=False) is None
    assert run("place_order", CLEAN, mode="chat") is None
    assert run("product_insight", {"inStock": True}) is None
    assert fast_reply.compose("voice", [1, 2], [SimpleNamespace(name="place_order", ok=True, result=CLEAN)] * 2) is None


def test_the_callers_words_and_tu(monkeypatch):
    monkeypatch.setenv("TEAM_FAST_REPLY", "1")
    two = {**CLEAN, "readback": "5 sacs de Farine de blé T55 tradition française, 2 pains de Levure fraîche ; livraison mercredi 25 novembre"}
    call = SimpleNamespace(name="place_order", arguments={"lines": [{"said": "tradi", "qty": 5}, {"said": "levure", "qty": 2}]})
    said = fast_reply.compose("voice", [call], [SimpleNamespace(name="place_order", ok=True, result=two)])
    assert "5 sacs de tradi et 2 pains de levure, et vous serez livrés mercredi 25 novembre." in said
    tu = [SimpleNamespace(role="assistant", content="Salut Thierry, qu'est-ce que je te mets ?")]
    said = fast_reply.compose("voice", [call], [SimpleNamespace(name="place_order", ok=True, result=two)], tu)
    assert "et tu seras livré mercredi" in said and any(said.endswith(a) for a in fast_reply.ASKS_TU)
    assert "vous" not in said
    edit = SimpleNamespace(name="place_order", arguments={"orderId": "ord_1", "lines": [{"said": "tradi", "qty": 12}]})
    assert "farine de blé T55" in fast_reply.compose("voice", [edit], [SimpleNamespace(name="place_order", ok=True, result=CLEAN)])


def test_confirmation(monkeypatch):
    monkeypatch.setenv("TEAM_FAST_REPLY", "1")
    assert run("confirm_order", {"confirmed": True}) in fast_reply.DONE
    assert "déjà validée" in run("confirm_order", {"confirmed": True, "alreadyConfirmed": True, "next": "…"})
    assert run("confirm_order", {"confirmed": False, "next": "Pas de oui clair"}) is None
