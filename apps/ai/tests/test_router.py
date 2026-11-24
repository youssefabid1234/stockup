"""TEAM_ROUTER: simple replies to the fast model; « D'accord, je regarde ça » only when there is something to look up."""

import pytest

from app.agent.router import is_simple_turn, pick_llm
from app.services import fillers

SIMPLE = [
    "C'est bon, validez.", "Validé.", "Oui.", "Ouais vas-y.", "Parfait, merci !", "Merci, au revoir.", "OK ça marche.",
    "Oui c'est bon.", "Non merci, c'est tout.", "D'accord.", "Bon d'accord, allez-y.", "Je confirme.",
]
NOT_SIMPLE = [
    "Oui mais mettez-en douze.", "C'est combien le sac ?", "Il me faudrait dix sacs de tradi pour jeudi.",
    "Finalement enlevez le seigle.", "C'est bon pour jeudi ?", "Oui, et rajoutez deux pains de levure.",
    "Non, plutôt vendredi.", "La livraison de ce matin, il manquait deux sacs.",
]


@pytest.mark.parametrize("said", SIMPLE)
def test_simple_replies(said):
    assert is_simple_turn(said)


@pytest.mark.parametrize("said", NOT_SIMPLE)
def test_replies_that_need_the_main_model(said):
    assert not is_simple_turn(said)


def test_pick_llm_follows_the_switch(monkeypatch):
    main, fast = object(), object()
    monkeypatch.delenv("TEAM_ROUTER", raising=False)
    assert pick_llm("C'est bon, validez.", main, lambda: fast) == (main, "principal")
    monkeypatch.setenv("TEAM_ROUTER", "1")
    assert pick_llm("C'est bon, validez.", main, lambda: fast) == (fast, "rapide")
    assert pick_llm("Oui mais mettez-en douze.", main, lambda: fast) == (main, "principal")

    def broken():
        raise RuntimeError("no fast model")

    assert pick_llm("Merci.", main, broken) == (main, "principal")


@pytest.mark.parametrize("said", SIMPLE)
def test_no_acknowledgement_for_a_confirmation(said):
    assert not fillers.needs_lookup(said)


@pytest.mark.parametrize(
    "said",
    ["Oui mais mettez-en douze.", "C'est combien le sac ?", "Il me faudrait dix sacs de tradi pour jeudi.",
     "Finalement enlevez le seigle.", "Non, plutôt vendredi."],
)
def test_acknowledgement_when_there_is_something_to_look_up(said):
    assert fillers.needs_lookup(said)


def test_erp_codes_are_never_said():
    from app.services.voice_reply import spoken_reply

    assert spoken_reply("C'est validé, Nadine. Votre commande CMD-2026-007543 est confirmée pour jeudi.") == (
        "C'est validé, Nadine. Votre commande est confirmée pour jeudi."
    )
    assert spoken_reply("La commande n° CMD-2026-000123, livrée demain.") == "La commande, livrée demain."
    assert spoken_reply("J'ai ajouté prd_0001 à la commande.") == "J'ai ajouté à la commande."
    assert spoken_reply("Dix-huit euros 90 le sac de 25 kilos.") == "Dix-huit euros 90 le sac de 25 kilos."
