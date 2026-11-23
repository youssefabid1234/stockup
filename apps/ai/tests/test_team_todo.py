"""
Team 12: what each brick must do, written as tests. They are SKIPPED until the owner removes the skip mark and
makes them pass (then they guard the brick for the rest of the night). One section per owner.
"""

from datetime import date

import pytest

from app.agent import rules_order, rules_sales

TODO = pytest.mark.skip(reason="TODO: remove this mark when you implement the brick")

# ── Amine Khalil · rules_order ─────────────────────────────────────────────────────────────────────────────────


def test_next_delivery_date_uses_client_days_and_cutoff():
    today = date(2026, 11, 24)  # mardi, business date of the pack (06h30)
    assert rules_order.next_delivery_date(today, ["tue", "thu", "sat"], "jeudi") == date(2026, 11, 26)
    assert rules_order.next_delivery_date(today, ["tue", "thu", "sat"], "mercredi") is None  # not delivered that day
    assert rules_order.next_delivery_date(today, ["tue", "thu", "sat"], "demain", now_hour=18) is None  # after 17h: J+2


def test_ten_of_tradi_means_ten_sacks():
    assert rules_order.sacks_from_words("sac 25 kg", 10, None) == 10
    assert rules_order.sacks_from_words("sac 25 kg", 50, "kg") == 2


# ── Daycem · rules_sales ───────────────────────────────────────────────────────────────────────────────────────


def test_sales_rules_follow_their_switch(monkeypatch):
    monkeypatch.delenv("TEAM_SALES_RULES", raising=False)
    assert rules_sales.sales_rules_section() == ""
    monkeypatch.setenv("TEAM_SALES_RULES", "1")
    assert "remplaçant" in rules_sales.sales_rules_section()


def test_sales_rules_stay_general():
    """The jury plays other clients and products: the rules must not name any of ours (facts come from the ERP)."""
    text = rules_sales.SALES_RULES.lower()
    for specific in ["sarrailh", "colomiers", "escaich", "gerbe", "nadine", "guy", "bernard", "julien",
                     "tourage", "82", "aop", "cli_", "prd_"]:
        assert specific not in text, f"rule mentions {specific!r}"


def test_refuses_substitution_from_preferences():
    prefs = "Tradition du Lauragais, tourage AOP exclusivement. Jamais de substitution sur le beurre."
    assert rules_sales.refuses_substitution(prefs, "Beurre de tourage AOP Charentes-Poitou 84 %")
    assert not rules_sales.refuses_substitution(prefs, "Chocolat de couverture noir 64 %")


def test_rank_alternatives_in_stock_and_promo_first():
    alts = [
        {"id": "a", "name": "Margarine", "available": 50, "clientPrice": 3.9},
        {"id": "b", "name": "Tourage 82 %", "available": 0, "clientPrice": 9.2},
        {"id": "c", "name": "Tourage 82 %", "available": 30, "clientPrice": 9.2, "promo": "-8 %"},
    ]
    assert [a["id"] for a in rules_sales.rank_alternatives(alts, "")][:2] == ["c", "a"]


# ── Mohamed Amine · fillers ────────────────────────────────────────────────────────────────────────────────────


async def test_filler_bank_warms_up_every_phrase():
    from app.clients.mock_speech import MockTTS
    from app.services.fillers import PHRASES, FillerBank

    bank = FillerBank()
    await bank.warm_up(MockTTS())
    assert {key: len(clips) for key, clips in bank.audio.items()} == {key: len(phrases) for key, phrases in PHRASES.items()}
    assert all(clip.data for clips in bank.audio.values() for clip in clips)


# ── Youssef · product_insight / call_context ───────────────────────────────────────────────────────────────────


@TODO
async def test_product_insight_returns_stock_price_and_ranked_alternatives():
    """Fake ERP with an out-of-stock product and two substitutes; check the output shape of interfaces.md §2."""
    raise NotImplementedError
