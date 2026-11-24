"""
Daycem · T3 in English too (the team switches to the English data pack: SEED_DIR_NAME=seed_en, data/seed_en).

The same functions read both languages, with no switch: a card is in French or in English. Real English sentences of
data/seed_en (translated by Youssef's script: one French sentence can have several English wordings). French must not
move: the French tests stay in test_rules_sales.py.
"""

import json
from pathlib import Path

import pytest

from app.agent import rules_sales
from app.agent.rules_sales import (
    card_rules,
    doc_substitutes,
    has_same_use_substitute,
    name_match,
    rank_alternatives,
    substitution_policy,
)
from app.config import settings

TOURAGE_AOP = "AOP Charentes-Poitou 84% laminating butter (2 kg sheet)"
COUVERTURE = "Dark couverture chocolate 64% (pistoles, 5 kg bag)"
SARRAILH = ("Lauragais tradition, exclusively AOP butter for laminating, white ground almonds. Never any substitution on "
            "the butter: Guy would rather run out than make viennoiserie with standard laminating butter.")  # c0001  # fmt: skip


# ── substitution_policy ──


@pytest.mark.parametrize("prefs, expected", [
    ("Pays by LCR at 30 days end of month. Accepts equivalent substitutions if informed.", "accepte"),  # 31 cards
    ("Easter chocolate pre-orders in February. Equivalent substitutions accepted if we are told.", "accepte"),  # 25
    ("Delivered Wed. Refuses substitutions: call before any change.", "refuse"),  # 21
    ("Delivered Wed, Sat. Substitutions refused: call before any change.", "refuse"),  # 15
    ("Pays by LCR at 30 days end of month. Delivered Mon, Thu.", "inconnu"),
])  # fmt: skip
def test_english_substitution_sentences(prefs, expected):
    assert substitution_policy(TOURAGE_AOP, prefs) == expected


def test_english_refusal_scoped_to_the_butter():
    assert substitution_policy(TOURAGE_AOP, SARRAILH) == "refuse"
    assert substitution_policy(COUVERTURE, SARRAILH) == "inconnu"


def test_english_note_without_being_told_means_yes_if_we_ask():
    note = "Does not want any substitution without being told: if a product is out of stock, call Julien before the truck leaves."
    assert substitution_policy(TOURAGE_AOP, "", [note]) == "accepte"


def _cards(lang_dir: str) -> dict[str, tuple[str, list[str]]] | None:
    f = Path(settings.data_dir) / lang_dir / "clients.json"
    if not f.exists():
        return None
    rows = json.loads(f.read_text(encoding="utf-8"))
    rows = rows if isinstance(rows, list) else rows.get("items", [])
    return {c["id"]: (c.get("preferences") or "", [n.get("text") or "" for n in c.get("notes") or []]) for c in rows}


def test_every_card_gets_the_same_answer_in_both_languages():
    fr, en = _cards("seed"), _cards("seed_en")
    if not fr or not en:
        pytest.skip("both data packs are needed (DATA_DIR/seed and DATA_DIR/seed_en)")
    names = {"seed": "Beurre de tourage AOP Charentes-Poitou 84 % (plaque 2 kg)", "seed_en": TOURAGE_AOP}
    diff = {cid: (substitution_policy(names["seed"], *fr[cid]), substitution_policy(names["seed_en"], *en[cid]))
            for cid in fr if substitution_policy(names["seed"], *fr[cid]) != substitution_policy(names["seed_en"], *en[cid])}  # fmt: skip
    # never a refusal read as a yes (or the reverse); at most the careful « ask first » instead of « propose »:
    # cli_0007 « standard laminating butter » shares two words with « AOP … laminating butter » in English only
    assert all(set(pair) == {"accepte", "demander"} for pair in diff.values()), diff
    assert len(diff) <= 1, diff


# ── card_rules: what the card forbids or imposes ──

CREAMS = ["Thick crème fraîche 30% (5 L tub)", "Pasteurised liquid whole egg (1 L carton)", "Whole UHT milk (1 L carton)"]
FROZEN = ["Raw frozen all-butter pain au chocolat 75 g (carton of 140)", "Raw frozen all-butter croissant 70 g (carton of 150)",
          "Raw mini viennoiserie assortment (carton of 210)"]  # fmt: skip
CHOCOLATES = ["Dark couverture chocolate 64% (pistoles, 5 kg bag)", "Hazelnut praline 50% (5 kg tub)",
              "Dark chocolate baking chips (5 kg bag)", "Cocoa powder 22-24% (1 kg bag)"]  # fmt: skip


def _alts(*names):
    return [{"id": f"p{i}", "name": n, "unit": "kg", "available": 10} for i, n in enumerate(names)]


def test_35_cream_only_never_thick():
    prefs = "Easter chocolate pre-orders in February. 35% cream only, never thick. Delivered Tue. Fri. Equivalent substitutions accepted if we are told."
    missing = "UHT liquid cream 35% (1 L carton)"
    assert rank_alternatives(_alts(*CREAMS), prefs, for_product_name=missing, substitutes={}) == []
    assert has_same_use_substitute("x", missing, _alts(*CREAMS), substitutes={}, preferences=prefs) is False


@pytest.mark.parametrize("prefs", ["Does not want frozen goods: everything is made in-house.",
                                   "Does not want frozen products: everything is homemade."])  # fmt: skip
def test_no_frozen_goods(prefs):
    ranked = rank_alternatives(_alts(*FROZEN), prefs, for_product_name="Raw frozen pain aux raisins 110 g (carton of 80)", substitutes={})
    assert [a["name"] for a in ranked] == ["Raw mini viennoiserie assortment (carton of 210)"]


@pytest.mark.parametrize("prefs", ["Lauragais traditional flour only.", "Traditional flour from the Lauragais only."])
def test_traditional_flour_only(prefs):
    alts = [{"id": "prd_0002", "name": "T55 baker's wheat flour (25 kg bag)", "unit": "piece", "available": 10}]
    missing = "T55 traditional French wheat flour (25 kg bag)"
    assert rank_alternatives(alts, prefs, for_product_id="prd_0001", for_product_name=missing, substitutes={"prd_0001": ["prd_0002"]}) == []
    # another flour missing: the rule only keeps flours, nothing changes
    other = rank_alternatives(alts, prefs, for_product_name="T65 country wheat flour (25 kg bag)", substitutes={})
    assert len(other) == 1


def test_couvertures_only():
    prefs = "Couvertures exclusively from Cacaos Garonne, origin Ecuador and Peru."
    ranked = rank_alternatives(_alts(*CHOCOLATES), prefs, for_product_name="White couverture chocolate 33% (pistoles, 5 kg bag)", substitutes={})
    assert [a["name"] for a in ranked] == [CHOCOLATES[0]]


def test_liquid_egg_products_only_keeps_liquid_eggs():
    # the English wording names the eggs: the French limit (« ovoproduits ») does not exist here
    alts = _alts("Free-range eggs, size M (tray of 30)", "Pasteurised liquid whole egg (1 L carton)")
    ranked = rank_alternatives(alts, "Liquid egg products only (HACCP).", for_product_name="Pasteurised liquid egg white (1 L carton)", substitutes={})
    assert [a["name"] for a in ranked] == ["Pasteurised liquid whole egg (1 L carton)"]


def test_delivery_and_substitution_sentences_exclude_nothing():
    assert card_rules("", ["Closed on Wednesdays: never deliver on that day."]) == [] or len(
        rank_alternatives(_alts(*FROZEN), "", notes=["Closed on Wednesdays: never deliver on that day."], substitutes={})) == 3
    assert card_rules(SARRAILH.split(". ")[1]) == []  # « Never any substitution… » is substitution_policy's


# ── name_match: same use, English names (the product is the LAST word: « UHT liquid cream ») ──


def test_cream_gets_the_other_cream_not_the_milk():
    ranked = rank_alternatives(_alts("Whole UHT milk (1 L carton)", "Pasteurised liquid whole egg (1 L carton)", "Thick crème fraîche 30% (5 L tub)"),
                               "", for_product_name="UHT liquid cream 35% (1 L carton)", substitutes={})  # fmt: skip
    assert ranked[0]["name"].startswith("Thick crème fraîche")


def test_dark_couverture_gets_the_other_dark_couverture():
    alts = _alts("White couverture chocolate 33% (pistoles, 5 kg bag)", "Milk couverture chocolate 38% (pistoles, 5 kg bag)",
                 "Hazelnut praline 50% (5 kg tub)", "Dark couverture chocolate 70% (pistoles, 5 kg bag)")  # fmt: skip
    ranked = rank_alternatives(alts, "", for_product_name=COUVERTURE, substitutes={})
    assert ranked[0]["name"].startswith("Dark couverture chocolate 70")


@pytest.mark.parametrize("missing, alternatives", [
    ("82% pastry butter (10 kg carton)", ["82% laminating butter (2 kg sheet)", "AOP Charentes-Poitou unsalted butter (carton of 10 × 1 kg)",
                                          "Puff pastry margarine (10 kg carton)", "Salted churned butter (1 kg block)"]),
    ("Roasted hazelnut powder (1 kg bag)", ["Walnut kernels (5 kg carton)", "Flaked almonds (1 kg bag)", "Blanched ground almonds (5 kg bag)"]),
    ("Frozen raspberry purée (1 kg tray)", ["Frozen par-baked baguette 280 g (carton of 60)", "Raw frozen all-butter croissant 70 g (carton of 150)"]),
])  # fmt: skip
def test_english_ranking_is_the_french_ranking(missing, alternatives):
    # « pastry » is shared with « Puff pastry margarine » in English only: the glossary compares the French originals
    from app.agent.rules_sales import _as_french

    if _as_french(missing) == missing:
        pytest.skip("needs data/seed_en/GLOSSARY.md")
    en = rank_alternatives(_alts(*alternatives), "", for_product_name=missing, substitutes={})
    fr = rank_alternatives(_alts(*map(_as_french, alternatives)), "", for_product_name=_as_french(missing), substitutes={})
    assert [a["id"] for a in en] == [a["id"] for a in fr]


def test_english_names_outside_the_glossary_use_the_last_word():
    assert name_match("Fresh goat cheese (pack of 6)", "Aged sheep cheese (1 kg block)") > name_match("Fresh goat cheese (pack of 6)", "Goat milk (1 L bottle)")


def test_french_names_outside_the_glossary_still_use_the_first_word():
    assert name_match("Fromage de chèvre frais (lot de 6)", "Fromage de brebis affiné (pain 1 kg)") > name_match("Fromage de chèvre frais (lot de 6)", "Lait de chèvre (bouteille 1 L)")


def test_strawberries_have_no_same_use_substitute_in_english_either():
    alts = _alts("Lemon (5 kg case)", "Golden pastry apple (13 kg case)")
    assert has_same_use_substitute("x", "Gariguette strawberry (500 g punnet)", alts, substitutes={}) is False


# ── doc_substitutes: read by id, whatever the language of the docs ──


def test_doc_substitutes_read_an_english_line(tmp_path):
    (tmp_path / "03-product-glossary.md").write_text(
        "## Usual substitutions\n\n- AOP Charentes-Poitou 84% laminating butter (2 kg sheet) (prd_0025) → 82% laminating butter (2 kg sheet) (prd_0026)\n",
        encoding="utf-8")  # fmt: skip
    assert doc_substitutes(tmp_path) == {"prd_0025": ["prd_0026"]}


# ── SALES_RULES_EN: ready, not wired (waiting for the team's language setting) ──


def test_english_sales_rules_are_used_when_enabled(monkeypatch):
    monkeypatch.setenv("TEAM_SALES_RULES", "1")
    assert rules_sales.SALES_RULES_EN.startswith("Sales rules")
    assert rules_sales.sales_rules_section() == rules_sales.SALES_RULES.strip()


def test_english_sales_rules_stay_general():
    text = rules_sales.SALES_RULES_EN.lower()
    for specific in ["sarrailh", "colomiers", "escaich", "gerbe", "nadine", "guy", "bernard", "julien",
                     "laminating", "tourage", "82", "aop", "cli_", "prd_"]:  # fmt: skip
        assert specific not in text, f"rule mentions {specific!r}"


def test_english_code_names_no_product():
    import inspect

    code = "".join(inspect.getsource(f) for f in (name_match, card_rules, substitution_policy, rules_sales._name_words)).lower()
    import re

    for word in ["cream", "butter", "flour", "chocolate", "strawberry", "frozen", "egg"]:
        assert not re.search(rf"\b{word}s?\b", code), f"code mentions {word!r}"
