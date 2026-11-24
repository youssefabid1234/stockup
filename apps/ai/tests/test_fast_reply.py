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
    assert run("place_order", CLEAN) == ("Je vous note 10 sacs de farine de blé T55 tradition française, livraison jeudi "
                                         "26 novembre, pour 189 euros hors taxes. Je vous la valide ?")
    franco = {**CLEAN, "totalHt": 3.0, "franco": "la commande fait 3 euros hors taxes : en dessous de 150 euros, il y a 12 euros de livraison"}
    assert "Attention, la commande fait 3 euros" in run("place_order", franco)


def test_anything_unusual_goes_back_to_the_model(monkeypatch):
    monkeypatch.setenv("TEAM_FAST_REPLY", "1")
    for extra in ({"alerts": ["compte bloqué"]}, {"askFirst": [{"productId": "p"}]}, {"sameDayOrders": [{"id": "o"}]},
                  {"duplicateDrafts": [{"id": "o"}]}, {"canConfirm": False}, {"written": False, "next": "Quel jour ?"}):
        assert run("place_order", {**CLEAN, **extra}) is None, extra
    assert run("place_order", CLEAN, ok=False) is None
    assert run("place_order", CLEAN, mode="chat") is None
    assert run("product_insight", {"inStock": True}) is None
    assert fast_reply.compose("voice", [1, 2], [SimpleNamespace(name="place_order", ok=True, result=CLEAN)] * 2) is None


def test_confirmation(monkeypatch):
    monkeypatch.setenv("TEAM_FAST_REPLY", "1")
    assert run("confirm_order", {"confirmed": True}).startswith("C'est validé")
    assert "déjà validée" in run("confirm_order", {"confirmed": True, "alreadyConfirmed": True, "next": "…"})
    assert run("confirm_order", {"confirmed": False, "next": "Pas de oui clair"}) is None
