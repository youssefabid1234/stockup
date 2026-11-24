"""
Daycem · T3 · does this client accept a substitute for this product? (agent/rules_sales.py)

Keywords first (92 of the 104 cards have a ready-made sentence), Jev only when no sentence is found, and the caller's
consent is always asked before a substitute is added (that part is in SALES_RULES). The texts below are the real
preferences / CRM notes of the cards (fictional data). Jev is faked: no network.
"""

import pytest

from app.agent import rules_sales
from app.agent.rules_sales import decide_substitution, substitution_policy

TOURAGE_AOP = "Charentes-Poitou AOP laminating butter, 84% (2 kg slab)"
COUVERTURE = "64% dark couverture chocolate"
CREME = "35% UHT whipping cream (1 L carton)"
SARRAILH = "AOP laminating butter only. Never substitute for butter: Guy would rather run out."
PETRIN_COLOMIERS = "Delivery before 11 am. Accepts equivalent substitutions with advance notice."
FOURNIL_BRIGITTE = "AOP laminating butter for pastries. Refuses substitutions: call before any change."
FOURNIL_BRIGITTE_NOTE = "No substitution without prior notice."
FOURNIL_GUILLAUME = "AOP laminating butter for pastries. Accepts equivalent substitutions with advance notice."
PETRIN_BALMA = "Orders traditional flour, yeast and standard butter twice a week."
PETRIN_BALMA_NOTE = "No substitution without being told. Call Romain before the truck leaves."
LES_CARMES = "Orders chocolate, cream and butter every week."
LES_CARMES_NOTE = "Never substitute for couverture without agreement."
HOTEL_GARONNE = "Needs all-butter mini pastries three times a week before 7 am."


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


# ── T3 · rank_alternatives: substitutes named in the company docs first ──

from app.agent.rules_sales import doc_substitutes, rank_alternatives  # noqa: E402

GLOSSARY = """## Usual Substitutions

- Touring butter AOP Charentes-Poitou 84% (plate 2 kg) (prd_0025) → Touring butter 82% (plate 2 kg) (prd_0026)
- Bourbon vanilla pods from Madagascar (package 100 g) (prd_0022) → Liquid vanilla extract (bottle 1 L) (prd_0023)
"""

# What GET /api/products/prd_0025/alternatives really returns (closest price first), trimmed
ERP_ALTERNATIVES_FOR_TOURAGE_AOP = [
    {"id": "prd_0029", "name": "Half-salt butter (motte 1 kg)", "category": "beurres", "available": 45.49, "price": 11.8},
    {"id": "prd_0027", "name": "Sweet butter AOP Charentes-Poitou (carton 10 × 1 kg)", "category": "beurres", "available": 893.36, "price": 10.2},
    {"id": "prd_0026", "name": "Touring butter 82 % (plate 2 kg)", "category": "beurres", "available": 1712.92, "price": 9.2},
    {"id": "prd_0028", "name": "Pastry butter 82 % (carton 10 kg)", "category": "beurres", "available": 933.71, "price": 7.6},
    {"id": "prd_0030", "name": "Sheeting margarine (carton 10 kg)", "category": "beurres", "available": 151.27, "price": 3.9},
]


def test_doc_substitutes_are_read_from_the_docs_without_product_names_in_code(tmp_path):
    (tmp_path / "03-glossaire.md").write_text(GLOSSARY, encoding="utf-8")
    assert doc_substitutes(tmp_path) == {"prd_0025": ["prd_0026"], "prd_0022": ["prd_0023"]}


def test_missing_docs_give_no_substitutes(tmp_path):
    assert doc_substitutes(tmp_path / "nowhere") == {}


def test_the_substitute_named_in_the_docs_comes_first_not_the_closest_price():
    subs = {"prd_0025": ["prd_0026"]}
    ranked = rank_alternatives(ERP_ALTERNATIVES_FOR_TOURAGE_AOP, "", for_product_id="prd_0025", substitutes=subs)
    assert ranked[0]["id"] == "prd_0026"
    assert [a["id"] for a in ranked[1:]] == ["prd_0029", "prd_0027", "prd_0028", "prd_0030"]  # then the ERP order


def test_an_out_of_stock_doc_substitute_never_goes_before_an_available_product():
    alts = [{**a, "available": 0} if a["id"] == "prd_0026" else a for a in ERP_ALTERNATIVES_FOR_TOURAGE_AOP]
    ranked = rank_alternatives(alts, "", for_product_id="prd_0025", substitutes={"prd_0025": ["prd_0026"]})
    assert ranked[-1]["id"] == "prd_0026"


def test_same_category_before_other_uses_then_promo():
    alts = [
        {"id": "x", "name": "Margarine", "category": "matieres-grasses", "available": 10, "promo": "-10 %"},
        {"id": "y", "name": "Pastry butter", "category": "beurres", "available": 10},
        {"id": "z", "name": "Sweet butter", "category": "beurres", "available": 10, "promo": "-5 %"},
    ]
    ranked = rank_alternatives(alts, "", for_product_id="prd_9999", for_category="beurres", substitutes={})
    assert [a["id"] for a in ranked] == ["z", "y", "x"]


def test_ranking_never_drops_or_changes_an_alternative():
    ranked = rank_alternatives(ERP_ALTERNATIVES_FOR_TOURAGE_AOP, "", for_product_id="prd_0025", substitutes={})
    assert sorted(map(str, ranked)) == sorted(map(str, ERP_ALTERNATIVES_FOR_TOURAGE_AOP))
    assert rank_alternatives([], "") == []


# ── T3 · same use: names that share distinctive words come first (when the docs name no substitute) ──
#
# Real names and ERP order (closest price first) of GET /api/products/{id}/alternatives, trimmed (audit 24/11).

from app.agent.rules_sales import has_same_use_substitute, name_match  # noqa: E402


def _alts(*names, unit="kg", available=10):
    return [{"id": f"p{i}", "name": n, "unit": unit, "available": available, "category": "c"} for i, n in enumerate(names)]


def _names(ranked):
    return [a["name"] for a in ranked]


def test_cream_gets_the_other_cream_not_the_liquid_egg():
    alts = _alts("Œuf entier liquide pasteurisé (brique 1 L)", "Crème fraîche épaisse 30 % (seau 5 L)",
                 "Blanc d'œuf liquide pasteurisé (brique 1 L)", "Lait entier UHT (brique 1 L)")  # fmt: skip
    ranked = rank_alternatives(alts, "", for_product_name="Crème liquide UHT 35 % (brique 1 L)", substitutes={})
    assert ranked[0]["name"].startswith("Crème fraîche")


def test_dark_chocolate_gets_the_other_dark_chocolate_not_the_white_one():
    alts = _alts("Chocolat de couverture blanc 33 % (pistoles, sac 5 kg)", "Chocolat de couverture lait 38 % (pistoles, sac 5 kg)",
                 "Praliné noisette 50 % (seau 5 kg)", "Chocolat de couverture noir 70 % (pistoles, sac 5 kg)")  # fmt: skip
    ranked = rank_alternatives(alts, "", for_product_name="Chocolat de couverture noir 64 % (pistoles, sac 5 kg)", substitutes={})
    assert ranked[0]["name"].startswith("Chocolat de couverture noir 70")


def test_sugar_gets_a_sugar_not_the_vanilla_extract():
    alts = [{"id": "v", "name": "Extrait de vanille liquide (bouteille 1 L)", "unit": "liter", "available": 5, "category": "c"},
            *_alts("Nappage neutre à chaud (seau 7 kg)", "Sucre en grains perlé (sac 10 kg)", "Sucre glace (sac 10 kg)", unit="piece")]  # fmt: skip
    ranked = rank_alternatives(alts, "", for_product_name="Sucre semoule (sac 25 kg)", substitutes={})
    assert ranked[0]["name"].startswith("Sucre en grains")


def test_egg_white_gets_the_whole_liquid_egg_not_the_cream():
    alts = _alts("Crème liquide UHT 35 % (brique 1 L)", "Œuf entier liquide pasteurisé (brique 1 L)", "Lait entier UHT (brique 1 L)")
    ranked = rank_alternatives(alts, "", for_product_name="Blanc d'œuf liquide pasteurisé (brique 1 L)", substitutes={})
    assert ranked[0]["name"].startswith("Œuf entier")


def test_the_docs_substitute_still_beats_a_closer_name():
    # « Beurre doux AOP Charentes-Poitou » shares more words with the AOP tourage, but the docs name the 82 % tourage
    ranked = rank_alternatives(ERP_ALTERNATIVES_FOR_TOURAGE_AOP, "", for_product_id="prd_0025",
                               for_product_name="Beurre de tourage AOP Charentes-Poitou 84 % (plaque 2 kg)",
                               substitutes={"prd_0025": ["prd_0026"]})  # fmt: skip
    assert ranked[0]["id"] == "prd_0026"


def test_in_stock_still_beats_a_closer_name():
    alts = [*_alts("Crème fraîche épaisse 30 % (seau 5 L)", available=0), *_alts("Lait entier UHT (brique 1 L)")]
    alts[1]["id"] = "lait"
    ranked = rank_alternatives(alts, "", for_product_name="Crème liquide UHT 35 % (brique 1 L)", substitutes={})
    assert ranked[0]["id"] == "lait"


def test_a_word_most_candidates_share_does_not_decide():
    farines = ["Farine de blé T65 campagne (sac 25 kg)", "Farine de blé T55 tradition française (sac 25 kg)",
               "Farine bise T80 (sac 25 kg)", "Farine de seigle T130 (sac 25 kg)"]  # fmt: skip
    ranked = rank_alternatives(_alts(*farines), "", for_product_name="Farine de blé T55 boulangère (sac 25 kg)", substitutes={})
    assert ranked[0]["name"].startswith("Farine de blé T55 tradition")  # « T55 » decides, not « farine » or « blé »
    assert name_match("Farine de gruau T45 pâtissière (sac 25 kg)", farines[3], farines) == 0


def test_packaging_numbers_and_units_never_count():
    assert name_match("Sel fin de mer (sac 25 kg)", "Sucre semoule (sac 25 kg)") == 0
    assert name_match("Boîtes pâtissières blanches 20 cm (lot de 50)", "Semelles dorées rondes 28 cm (lot de 100)") == 0


def test_plural_and_feminine_forms_match():
    assert name_match("Œufs plein air calibre M (plateau de 30)", "Œuf entier liquide pasteurisé (brique 1 L)") > 0
    assert name_match("Pain aux raisins cru surgelé 110 g", "Croissant pur beurre crue surgelée") > 0


def test_same_unit_breaks_a_tie():
    alts = [{"id": "l", "name": "Eau de fleur d'oranger (bidon 1 L)", "unit": "liter", "available": 5},
            {"id": "s", "name": "Sucre glace (sac 10 kg)", "unit": "piece", "available": 5}]  # fmt: skip
    ranked = rank_alternatives(alts, "", for_product_name="Sel fin de mer (sac 25 kg)", for_unit="piece", substitutes={})
    assert ranked[0]["id"] == "s"


def test_without_the_missing_name_the_order_is_unchanged():
    alts = _alts("Œuf entier liquide pasteurisé (brique 1 L)", "Crème fraîche épaisse 30 % (seau 5 L)")
    assert _names(rank_alternatives(alts, "", substitutes={})) == _names(alts)


def test_name_ranking_never_drops_or_changes_an_alternative():
    alts = _alts("Œuf entier liquide pasteurisé (brique 1 L)", "Crème fraîche épaisse 30 % (seau 5 L)", "Lait entier UHT (brique 1 L)")
    ranked = rank_alternatives(alts, "", for_product_name="Crème liquide UHT 35 % (brique 1 L)", substitutes={})
    assert sorted(map(str, ranked)) == sorted(map(str, alts))


# ── B · is there a substitute with the same use at all? (product_insight then says so instead of proposing one) ──


def test_no_same_use_substitute_for_strawberries_among_lemons_and_apples():
    alts = _alts("Citron jaune (colis 5 kg)", "Pomme Golden pâtissière (colis 13 kg)")
    assert has_same_use_substitute("prd_x", "Fraise Gariguette (barquette 500 g)", alts, substitutes={}) is False


def test_a_name_sharing_a_distinctive_word_is_a_same_use_substitute():
    alts = _alts("Œuf entier liquide pasteurisé (brique 1 L)", "Crème fraîche épaisse 30 % (seau 5 L)")
    assert has_same_use_substitute("prd_x", "Crème liquide UHT 35 % (brique 1 L)", alts, substitutes={}) is True


def test_a_docs_substitute_in_stock_is_always_a_same_use_substitute():
    alts = [{"id": "prd_y", "name": "Tout autre nom", "available": 3}]
    assert has_same_use_substitute("prd_x", "Un produit", alts, substitutes={"prd_x": ["prd_y"]}) is True
    assert has_same_use_substitute("prd_x", "Un produit", [{**alts[0], "available": 0}], substitutes={"prd_x": ["prd_y"]}) is False


def test_no_name_means_we_cannot_tell_so_we_keep_proposing():
    assert has_same_use_substitute("prd_x", "", _alts("Citron jaune"), substitutes={}) is True


def test_same_use_code_names_no_product():
    """General for any data pack: the ranking code knows no product, only how names are written."""
    import inspect

    code = "".join(inspect.getsource(f) for f in (name_match, has_same_use_substitute, rank_alternatives, rules_sales._name_words,
                                                  card_rules, allowed_by_card)).lower()
    for word in ["creme", "crème", "sucre", "farine", "chocolat", "beurre", "tourage", "oeuf", "œuf", "fraise", "citron", "prd_"]:
        assert word not in code, f"ranking code mentions {word!r}"


def test_the_family_word_is_enough_to_be_a_same_use_substitute():
    # it decides nothing in the RANKING (every butter has it), but it does say « same use » (audit: 82 % tourage)
    alts = _alts("Beurre doux AOP Charentes-Poitou (carton 10 × 1 kg)", "Beurre pâtissier 82 % (carton 10 kg)")
    assert has_same_use_substitute("prd_x", "Beurre de tourage 82 % (plaque 2 kg)", alts, substitutes={}) is True


# ── T3 · what the client's card forbids (« jamais de… ») or imposes (« … uniquement ») is never proposed ──
#
# Real sentences of the cards (audit 24/11, list checked by Daycem): 29 cards. Real catalogue names.

from app.agent.rules_sales import allowed_by_card, card_rules  # noqa: E402

CREME_ONLY = "Précommandes de chocolat de Pâques en février. Crème 35 % uniquement, jamais d'épaisse. Livré mar. ven. Accepte les substitutions équivalentes si on prévient."  # c0053  # fmt: skip
NO_FROZEN = "Ne veut pas de surgelé : tout est fait maison."  # c0074 and 9 others
TRADITION_ONLY = "Farine de tradition du Lauragais uniquement."  # c0024 and 7 others
COUVERTURES_ONLY = "Couvertures exclusivement Cacaos Garonne, origine Équateur et Pérou."  # c0002
OVO_ONLY = "Ovoproduits liquides uniquement (HACCP)."  # c0082
DELIVERY_NOTE = "Jamais de livraison ce jour-là."  # 18 CRM notes
MAILS_NOTE = "Philippe ne lit pas les mails de relance."

CREMES = ["Crème fraîche épaisse 30 % (seau 5 L)", "Œuf entier liquide pasteurisé (brique 1 L)", "Lait entier UHT (brique 1 L)"]
SURGELES = ["Chocolatine pur beurre crue surgelée 75 g (carton 140)", "Croissant pur beurre cru surgelé 70 g (carton 150)",
            "Assortiment mini-viennoiseries crues (carton 210)"]  # fmt: skip
FARINES = ["Farine de blé T55 boulangère (sac 25 kg)", "Farine de blé T65 campagne (sac 25 kg)", "Farine bise T80 (sac 25 kg)"]
CHOCOLATS = ["Chocolat de couverture noir 64 % (pistoles, sac 5 kg)", "Praliné noisette 50 % (seau 5 kg)",
             "Pépites de chocolat noir cuisson (sac 5 kg)", "Cacao en poudre 22-24 % (sac 1 kg)"]  # fmt: skip


def test_never_the_thick_cream_for_a_client_who_says_never():
    ranked = rank_alternatives(_alts(*CREMES), CREME_ONLY, for_product_name="Crème liquide UHT 35 % (brique 1 L)", substitutes={})
    assert not any("épaisse" in a["name"] for a in ranked)


def test_cream_35_only_leaves_nothing_when_the_35_cream_is_missing():
    assert rank_alternatives(_alts(*CREMES), CREME_ONLY, for_product_name="Crème liquide UHT 35 % (brique 1 L)", substitutes={}) == []
    assert has_same_use_substitute("prd_x", "Crème liquide UHT 35 % (brique 1 L)", _alts(*CREMES), substitutes={},
                                   preferences=CREME_ONLY) is False  # fmt: skip


def test_no_frozen_product_for_a_client_who_wants_none_even_in_the_feminine():
    ranked = rank_alternatives(_alts(*SURGELES), NO_FROZEN, for_product_name="Pain aux raisins cru surgelé 110 g (carton 80)", substitutes={})
    assert _names(ranked) == ["Assortiment mini-viennoiseries crues (carton 210)"]


def test_tradition_only_means_no_other_flour_when_the_tradition_is_missing():
    missing = "Farine de blé T55 tradition française (sac 25 kg)"
    alts = [{"id": "prd_0002", "name": FARINES[0], "unit": "piece", "available": 10}]
    # even the substitute the docs name is not proposed: the card wins
    assert rank_alternatives(alts, TRADITION_ONLY, for_product_id="prd_0001", for_product_name=missing,
                             substitutes={"prd_0001": ["prd_0002"]}) == []  # fmt: skip
    assert has_same_use_substitute("prd_0001", missing, alts, substitutes={"prd_0001": ["prd_0002"]}, preferences=TRADITION_ONLY) is False


def test_an_only_rule_on_another_product_changes_nothing():
    ranked = rank_alternatives(_alts(*CHOCOLATS), TRADITION_ONLY, for_product_name="Chocolat de couverture noir 70 % (pistoles, sac 5 kg)", substitutes={})
    assert sorted(_names(ranked)) == sorted(CHOCOLATS)


def test_couvertures_only_keeps_only_couvertures():
    ranked = rank_alternatives(_alts(*CHOCOLATS), COUVERTURES_ONLY, for_product_name="Chocolat de couverture blanc 33 % (pistoles, sac 5 kg)", substitutes={})
    assert _names(ranked) == ["Chocolat de couverture noir 64 % (pistoles, sac 5 kg)"]


def test_ovoproducts_only_is_ignored_no_product_name_says_ovoproduct():
    # known limit (docs/team/t3-ranking-audit.md): no false positive on the liquid cream or the vanilla extract
    assert card_rules(OVO_ONLY) == [] or all(
        allowed_by_card("Crème liquide UHT 35 % (brique 1 L)", n, card_rules(OVO_ONLY)) for n in CREMES)
    alts = _alts("Œufs plein air calibre M (plateau de 30)", "Jaune d'œuf liquide pasteurisé (brique 1 L)")
    assert len(rank_alternatives(alts, OVO_ONLY, for_product_name="Blanc d'œuf liquide pasteurisé (brique 1 L)", substitutes={})) == 2


def test_sentences_about_delivery_or_mails_exclude_nothing():
    ranked = rank_alternatives(_alts(*SURGELES), "", notes=[DELIVERY_NOTE, MAILS_NOTE],
                               for_product_name="Pain aux raisins cru surgelé 110 g (carton 80)", substitutes={})  # fmt: skip
    assert len(ranked) == 3


def test_a_note_can_forbid_too():
    ranked = rank_alternatives(_alts(*SURGELES), "", notes=[NO_FROZEN], for_product_name="Pain aux raisins cru surgelé 110 g", substitutes={})
    assert len(ranked) == 1


def test_substitution_sentences_are_left_to_substitution_policy():
    assert card_rules("Jamais de substitution sur le beurre.") == []
    assert card_rules("Refuse les substitutions : appeler avant toute modification.") == []


def test_no_preferences_no_change():
    alts = _alts(*CREMES)
    assert rank_alternatives(alts, "", for_product_name="Crème liquide UHT 35 % (brique 1 L)", substitutes={}) != []
    assert card_rules("") == []
