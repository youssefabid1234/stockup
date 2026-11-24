"""Youssef · the first words fit what the caller just said: nothing before a goodbye, a leading « bonjour » ignored."""

import pytest

from app.services.fillers import intent_of, is_closing, request_part


@pytest.mark.parametrize("said", [
    "Parfait, merci beaucoup. Je n'ai rien d'autre. Au revoir.", "Non c'est tout, merci, au revoir.", "Merci, bonne journée !",
    "Ce sera tout pour aujourd'hui.", "Bon ben je vais vous laisser, à bientôt.", "Adieu, au revoir. Bonne soirée.",
])
def test_a_goodbye_is_a_closing(said):
    assert is_closing(said)


@pytest.mark.parametrize("said", [
    "Bonjour, il me faudrait deux sacs de tradi pour jeudi.", "C'est tout, ah et aussi 2 sacs de seigle.",
    "Vous livrez jeudi ?", "Mettez-moi 3 cartons de beurre.",
])
def test_a_request_is_not_a_closing(said):
    assert not is_closing(said)


def test_a_leading_greeting_does_not_choose_the_phrase():
    assert request_part("Bonjour, oui, alors il me faudrait deux sacs") == "il me faudrait deux sacs"
    assert intent_of(request_part("Bonjour Lucie, c'est combien le sac de tradi ?")) == "price"
    assert intent_of(request_part("Oui bonjour, vous avez encore du beurre ?")) == "stock"
