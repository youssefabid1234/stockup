"""
Daycem · T3 · does this client accept a substitute for this product? (agent/rules_sales.py)

Keywords first (92 of the 104 cards have a ready-made sentence), Jev only when no sentence is found, and the caller's
consent is always asked before a substitute is added (that part is in SALES_RULES). The texts below are the real
preferences / CRM notes of the cards (fictional data). Jev is faked: no network.
"""

import pytest

from app.agent import rules_sales
from app.agent.rules_sales import decide_substitution, substitution_policy

TOURAGE_AOP = "Beurre de tourage AOP Charentes-Poitou 84 % (plaque 2 kg)"
COUVERTURE = "Chocolat de couverture noir 64 %"
CREME = "Crème liquide UHT 35 % (brique 1 l)"

SARRAILH = (  # c0001
    "Tradition du Lauragais, tourage AOP exclusivement, poudre d'amande blanche. Jamais de substitution sur le beurre : "
    "Guy préfère manquer que faire de la viennoiserie au tourage standard."
)
PETRIN_COLOMIERS = (  # c0021
    "Paye en LCR à 30 jours fin de mois. Livraison avant 11h, après le rush du matin. Livré lun. mer. "
    "Accepte les substitutions équivalentes si on prévient."
)
FOURNIL_BRIGITTE = (  # c0097
    "Tourage AOP pour la viennoiserie, beurre pâtissier pour le reste. Farine de tradition du Lauragais uniquement. "
    "Livré mer. sam. Refuse les substitutions : appeler avant toute modification."
)
FOURNIL_BRIGITTE_NOTE = "Ne veut aucune substitution sans être prévenu : si un produit manque, appeler Maxime avant le départ du camion."
FOURNIL_GUILLAUME = (  # c0102
    "Livraison avant 11h, après le rush du matin. Tourage AOP pour la viennoiserie, beurre pâtissier pour le reste. "
    "Livré mar. ven. Accepte les substitutions équivalentes si on prévient."
)
PETRIN_BALMA = "Commandait deux fois par semaine : tradition, levure, tourage standard."  # c0007
PETRIN_BALMA_NOTE = "Ne veut aucune substitution sans être prévenu : si un produit manque, appeler Romain avant le départ du camion."
LES_CARMES = "Commandait chaque semaine chocolat, crème et beurre AOP."  # c0012
LES_CARMES_NOTE = "Ne jamais substituer une couverture sans accord."
HOTEL_GARONNE = "Cherche des mini-viennoiseries pur beurre livrées trois fois par semaine avant 7h."  # c0010


# ── keywords ──


def test_refusal_scoped_to_butter_covers_tourage_only():  # c0001
    assert substitution_policy(TOURAGE_AOP, SARRAILH) == "refuse"
    assert substitution_policy(COUVERTURE, SARRAILH) == "inconnu"  # the refusal is about butter, nothing else is said


def test_ready_made_acceptance():  # c0021
    assert substitution_policy(TOURAGE_AOP, PETRIN_COLOMIERS) == "accepte"


def test_refusal_in_preferences_wins_over_a_softer_note():  # c0097
    assert substitution_policy(TOURAGE_AOP, FOURNIL_BRIGITTE, [FOURNIL_BRIGITTE_NOTE]) == "refuse"


def test_acceptance_but_the_preferences_name_this_product_means_ask():  # c0102
    assert substitution_policy(TOURAGE_AOP, FOURNIL_GUILLAUME) == "demander"
    assert substitution_policy(CREME, FOURNIL_GUILLAUME) == "accepte"  # the named product is the tourage, not the cream


def test_no_substitute_without_being_told_means_accept_on_the_phone():  # c0007
    assert substitution_policy(TOURAGE_AOP, PETRIN_BALMA, [PETRIN_BALMA_NOTE]) == "accepte"


def test_scoped_note_on_another_product_says_nothing_about_this_one():  # c0012
    assert substitution_policy(TOURAGE_AOP, LES_CARMES, [LES_CARMES_NOTE]) == "inconnu"
    assert substitution_policy(COUVERTURE, LES_CARMES, [LES_CARMES_NOTE]) == "accepte"  # « sans accord » = with consent


def test_nothing_said():  # c0010
    assert substitution_policy(TOURAGE_AOP, HOTEL_GARONNE) == "inconnu"
    assert substitution_policy(TOURAGE_AOP, "") == "inconnu"


def test_refuses_substitution_keeps_its_contract():  # interfaces.md §5, used by product_insight
    assert rules_sales.refuses_substitution(SARRAILH, TOURAGE_AOP) is True
    assert rules_sales.refuses_substitution(SARRAILH, COUVERTURE) is False
    assert rules_sales.refuses_substitution(FOURNIL_GUILLAUME, TOURAGE_AOP) is False  # « demander » is not a refusal


# ── keywords, then Jev ──


class FakeJev:
    def __init__(self, p_yes: float):
        self.p_yes, self.calls = p_yes, 0

    async def yes_no(self, state, question, yes=None, no=None) -> float:
        self.calls += 1
        return self.p_yes


async def test_keywords_decide_without_calling_jev():
    jev = FakeJev(0.99)
    assert await decide_substitution(TOURAGE_AOP, SARRAILH, jev=jev) == "refuse"
    assert await decide_substitution(TOURAGE_AOP, PETRIN_COLOMIERS, jev=jev) == "accepte"
    assert await decide_substitution(TOURAGE_AOP, FOURNIL_GUILLAUME, jev=jev) == "demander"
    assert jev.calls == 0


@pytest.mark.parametrize(("p_yes", "expected"), [(0.9, "accepte"), (0.1, "refuse"), (0.5, "demander")])
async def test_jev_only_when_no_sentence_is_found(p_yes, expected):
    jev = FakeJev(p_yes)
    assert await decide_substitution(TOURAGE_AOP, HOTEL_GARONNE, jev=jev) == expected
    assert jev.calls == 1


async def test_without_jev_or_when_jev_fails_ask_the_client():
    assert await decide_substitution(TOURAGE_AOP, HOTEL_GARONNE, jev=None) == "demander"

    class BrokenJev:
        async def yes_no(self, *args, **kwargs):
            raise TimeoutError

    assert await decide_substitution(TOURAGE_AOP, HOTEL_GARONNE, jev=BrokenJev()) == "demander"
