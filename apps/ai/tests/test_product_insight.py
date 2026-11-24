"""Youssef · T1 product_insight: one call = stock + this client's price + ranked substitutes with promo (fake ERP)."""

import asyncio

import pytest

from app.tools import insight
from app.tools.erp import ErpError

AOP, T82, DEMI_SEL, MARGARINE = "prd_0025", "prd_0026", "prd_0029", "prd_0030"
PROMO_RULE = {"id": "prl_demo", "name": "Promo tourage 82 % : −8 % jusqu'au 30/11", "validTo": "2026-11-30"}
GROUP_RULE = {"id": "prl_0001", "name": "Boulangeries : −4 % sur les farines dès 10 sacs", "validTo": None}


class FakeErp:
    def __init__(self, *, aop_available=0.0, preferences="Accepte les substitutions si on le prévient.", fail_price_for=(), delay=0.0):
        self.products = {
            AOP: {"id": AOP, "name": "Beurre de tourage AOP Charentes-Poitou (plaque 2 kg)", "unit": "kg", "price": 13.9,
                  "available": aop_available, "category": "beurres"},
        }  # fmt: skip
        self.alternatives = [  # the ERP's order: closest price first (salted butter before the 82 % tourage)
            {"id": DEMI_SEL, "name": "Beurre demi-sel de baratte", "unit": "kg", "price": 11.8, "available": 45, "category": "beurres"},
            {"id": T82, "name": "Beurre de tourage 82 % (plaque 2 kg)", "unit": "kg", "price": 9.2, "available": 1682, "category": "beurres"},
            {"id": MARGARINE, "name": "Margarine de feuilletage", "unit": "kg", "price": 3.9, "available": 151, "category": "beurres"},
        ]  # fmt: skip
        self.preferences = preferences
        self.fail_price_for = set(fail_price_for)
        self.delay = delay
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append(path)
        await asyncio.sleep(self.delay)
        if path == "/api/price-rules":
            return {"items": [PROMO_RULE, GROUP_RULE]}
        if path.startswith("/api/clients/"):
            return {"id": "cli_0021", "name": "Le Pétrin de Colomiers", "preferences": self.preferences,
                    "notes": [{"at": "2025-09-01T10:34:00Z", "author": "Karim", "text": "Fermé le mercredi."}]}  # fmt: skip  (real ERP shape)
        if path.endswith("/alternatives"):
            return self.alternatives
        if path.startswith("/api/products/"):
            pid = path.rsplit("/", 1)[-1]
            if pid not in self.products:
                raise ErpError("Produit introuvable : " + pid)
            return self.products[pid]
        if path == "/api/prices/resolve":
            pid = params["productId"]
            if pid in self.fail_price_for:
                raise ErpError("prix indisponible")
            if pid == T82:  # Daycem's demo promo: −8 % on the list price
                return {"price": 8.46, "listPrice": 9.2, "source": "rule", "explanation": "Règle « Promo tourage 82 % »",
                        "candidates": [{"source": "rule", "ruleId": "prl_demo", "price": 8.46, "applied": True}]}  # fmt: skip
            if pid == DEMI_SEL:  # a permanent group discount: a lower price, but NOT a promo
                return {"price": 11.33, "listPrice": 11.8, "source": "rule", "explanation": "Règle « Boulangeries »",
                        "candidates": [{"source": "rule", "ruleId": "prl_0001", "price": 11.33, "applied": True}]}  # fmt: skip
            price = {AOP: 13.9, MARGARINE: 3.9}[pid]
            return {"price": price, "listPrice": price, "source": "list", "explanation": f"Prix catalogue : {price} €", "candidates": []}
        raise AssertionError(path)


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    insight.clear_cache()
    # the company docs say « Tourage AOP (prd_0025) → Tourage 82 % (prd_0026) » (Daycem's doc_substitutes)
    from app.agent import rules_sales

    monkeypatch.setattr(rules_sales, "doc_substitutes", lambda folder=None: {AOP: [T82]})
    yield
    insight.clear_cache()


async def test_out_of_stock_aop_gives_the_82_tourage_first_with_its_promo():
    r = await insight.gather_insight(FakeErp(), "cli_0021", AOP, 10)
    assert r["inStock"] is False and r["product"]["available"] == 0
    assert r["product"]["clientPrice"] == 13.9
    assert r["substitution"] == "accepte"
    first = r["alternatives"][0]
    assert first["id"] == T82  # the house's substitute, before the closer-priced salted butter (ERP order)
    assert first["clientPrice"] == 8.46 and first["promo"]["pctOff"] == 8 and first["promo"]["until"] == "2026-11-30"
    assert "promo" not in r["alternatives"][1]  # the group discount on salted butter is not a promo
    assert all("category" not in a for a in r["alternatives"])


async def test_in_stock_product_returns_no_alternatives_and_no_second_wave():
    erp = FakeErp(aop_available=50)
    r = await insight.gather_insight(erp, "cli_0021", AOP, 10)
    assert r["inStock"] is True and r["alternatives"] == []
    assert "substitution" not in r
    assert erp.calls.count("/api/prices/resolve") == 1  # only the product's own price


async def test_partial_stock_says_how_much_is_missing():
    r = await insight.gather_insight(FakeErp(aop_available=4), "cli_0021", AOP, 10)
    assert r["inStock"] is False and r["missing"] == 6
    assert r["alternatives"][0]["id"] == T82


async def test_client_who_refuses_substitution_gets_no_alternative():
    erp = FakeErp(preferences="Jamais de substitution sur le beurre.")
    r = await insight.gather_insight(erp, "cli_0001", AOP, 10)
    assert r["substitution"] == "refuse" and r["alternatives"] == []
    assert "refuse" in r["note"]
    assert erp.calls.count("/api/prices/resolve") == 1  # no price asked for substitutes we won't offer


async def test_a_refusal_written_in_a_crm_note_counts_too():
    erp = FakeErp(preferences="")

    async def card(path, params=None, _get=erp.get):
        if path.startswith("/api/clients/"):
            return {"preferences": "", "notes": [{"text": "Guy : jamais de substitution sur le beurre."}]}
        return await _get(path, params)

    erp.get = card
    r = await insight.gather_insight(erp, "cli_0001", AOP, 10)
    assert r["substitution"] == "refuse"


async def test_unknown_product_raises_a_clear_erp_error():
    with pytest.raises(ErpError, match="introuvable"):
        await insight.gather_insight(FakeErp(), "cli_0021", "prd_9999", 1)


async def test_one_failing_price_does_not_hide_the_other_substitutes():
    r = await insight.gather_insight(FakeErp(fail_price_for={DEMI_SEL}), "cli_0021", AOP, 10)
    ids = [a["id"] for a in r["alternatives"]]
    assert set(ids) == {T82, DEMI_SEL, MARGARINE}
    demi = next(a for a in r["alternatives"] if a["id"] == DEMI_SEL)
    assert demi["clientPrice"] is None and demi["listPrice"] == 11.8


async def test_reads_run_in_parallel():
    # 5 reads in wave 1 + 3 prices in wave 2, 50 ms each: sequential would be ≥ 400 ms, parallel ≈ 100 ms
    loop = asyncio.get_running_loop()
    start = loop.time()
    await insight.gather_insight(FakeErp(delay=0.05), "cli_0021", AOP, 10)
    assert loop.time() - start < 0.25


async def test_expected_arrivals_are_given_so_no_get_product_stock_is_needed():
    erp = FakeErp()
    erp.products[AOP]["stock"] = {"incoming": 200.0}
    r = await insight.gather_insight(erp, "cli_0001", AOP, 10)
    assert r["product"]["incoming"] == 200.0
    r = await insight.gather_insight(FakeErp(), "cli_0001", AOP, 10)
    assert "incoming" not in r["product"]  # nothing expected: not even a 0 to read


async def test_no_qty_means_any_stock_is_enough():
    r = await insight.gather_insight(FakeErp(aop_available=1), "cli_0021", AOP, None)
    assert r["inStock"] is True


def test_promo_needs_an_applied_time_limited_rule_below_list_price():
    rules = {"prl_demo": PROMO_RULE, "prl_0001": GROUP_RULE}
    applied = lambda rid, price: {"source": "rule", "price": price, "listPrice": 9.2,  # noqa: E731
                                  "candidates": [{"ruleId": rid, "applied": True}]}  # fmt: skip
    assert insight.promo_of(applied("prl_demo", 8.46), rules)["name"].startswith("Promo")
    assert insight.promo_of(applied("prl_0001", 8.46), rules) is None  # no end date
    assert insight.promo_of(applied("prl_demo", 9.5), rules) is None  # not cheaper
    assert insight.promo_of({"source": "list", "price": 9.2, "listPrice": 9.2}, rules) is None
    assert insight.promo_of(None, rules) is None


def test_prompt_rule_only_when_switch_on(monkeypatch):
    monkeypatch.delenv("TEAM_PRODUCT_INSIGHT", raising=False)
    assert insight.product_insight_section() == ""
    monkeypatch.setenv("TEAM_PRODUCT_INSIGHT", "1")
    assert "product_insight" in insight.product_insight_section()
