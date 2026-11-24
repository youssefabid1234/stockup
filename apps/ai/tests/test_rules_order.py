"""Team 12 · Amine Khalil · deterministic helpers of agent/rules_order.py (dates of delivery, units)."""

from datetime import date

from app.agent import rules_order as ro
from app.tools.delivery import pack_now

TUE = date(2026, 11, 24)  # business date of the pack, 06h30
SARRAILH = ["tue", "thu", "sat"]
LAURAGAIS = ["tue", "fri"]


def test_weekday_names_and_relative_days():
    assert ro.next_delivery_date(TUE, SARRAILH, "Thursday") == date(2026, 11, 26)
    assert ro.next_delivery_date(TUE, SARRAILH, "Next Thursday") == date(2026, 11, 26)
    assert ro.next_delivery_date(TUE, SARRAILH, "Saturday") == date(2026, 11, 28)
    assert ro.next_delivery_date(TUE, SARRAILH, "the day after tomorrow") == date(2026, 11, 26)
    assert ro.next_delivery_date(TUE, SARRAILH, "Tuesday") == date(2026, 12, 1)  # said on a Tuesday = next Tuesday
    assert ro.next_delivery_date(TUE, SARRAILH, "on 28") == date(2026, 11, 28)
    assert ro.next_delivery_date(TUE, SARRAILH, "26/11") == date(2026, 11, 26)


def test_day_not_delivered_or_gone():
    assert ro.next_delivery_date(TUE, SARRAILH, "Wednesday") is None
    assert ro.next_delivery_date(TUE, SARRAILH, "tomorrow") is None  # Wednesday
    assert ro.next_delivery_date(TUE, SARRAILH, "Today") is None  # routes left at 06h30
    assert ro.next_delivery_date(TUE, SARRAILH, "Anytime this thing") is None


def test_asap_is_first_possible_day():
    assert ro.next_delivery_date(TUE, SARRAILH, "as soon as possible") == date(2026, 11, 26)
    assert ro.next_delivery_date(TUE, SARRAILH, None) == date(2026, 11, 26)
    assert ro.next_delivery_date(TUE, ["mon", "wed", "fri"], "as soon as possible") == date(2026, 11, 25)
    assert ro.next_delivery_date(TUE, [], None) is None


def test_cutoffs():
    wed_clients = ["mon", "wed", "fri"]
    assert ro.next_delivery_date(TUE, wed_clients, "tomorrow", now_hour=16.9) == date(2026, 11, 25)
    assert ro.next_delivery_date(TUE, wed_clients, "tomorrow", now_hour=17) is None  # after 17h: too late for tomorrow
    assert ro.next_delivery_date(TUE, wed_clients, None, now_hour=18) == date(2026, 11, 27)
    # Lauragais-Tarn: order the day before before noon; Friday is still fine on Tuesday
    assert ro.next_delivery_date(TUE, LAURAGAIS, "Friday", cutoff_hour=12) == date(2026, 11, 27)
    thu = date(2026, 11, 26)
    assert ro.next_delivery_date(thu, LAURAGAIS, "Friday", now_hour=11, cutoff_hour=12) == date(2026, 11, 27)
    assert ro.next_delivery_date(thu, LAURAGAIS, "Friday", now_hour=13, cutoff_hour=12) is None


def test_delivery_answer_for_the_agent():
    ok = ro.delivery_answer(TUE, SARRAILH, "Thursday", 6.5)
    assert ok == {"deliveryDays": ["Tuesday", "Thursday", "Saturday"], "ok": True, "date": "2026-11-26", "say": "Thursday 26 November"}
    no = ro.delivery_answer(TUE, SARRAILH, "Wednesday", 6.5)
    assert no["ok"] is False and "Wednesday" in no["reason"]
    assert no["nextPossible"] == "2026-11-26" and no["sayNext"] == "Thursday 26 November"
    gone = ro.delivery_answer(TUE, LAURAGAIS, "this morning", 6.5, zone="Lauragais & Tarn")
    assert gone["ok"] is False and "depot" in gone["reason"] and gone["nextPossible"] == "2026-11-27"
    late = ro.delivery_answer(date(2026, 11, 26), LAURAGAIS, "Friday", 14, zone="Lauragais & Tarn")
    assert late["ok"] is False and "noon" in late["reason"] and late["nextPossible"] == "2026-12-01"


def test_units():
    assert ro.sacks_from_words("25 kg sack", 10, None) == 10  # « 10 de tradi »
    assert ro.sacks_from_words("25 kg sack", 10, "sacs") == 10
    assert ro.sacks_from_words("25 kg sack", 50, "kilos") == 2
    assert ro.sacks_from_words("10 kg sack", 30, "kg") == 3  # Spell
    assert ro.sacks_from_words("25 kg sack", 40, "kg") == 1.6  # not a whole sack: the agent asks
    assert ro.sacks_from_words("kg", 40, "kilos") == 40  # tourage is sold by the kilo
    assert ro.sacks_from_words("carton 140", 4, None) == 4


def test_pack_now_reads_the_pack_clock():
    assert pack_now({"today": "2026-11-24", "generatedAt": "2026-11-24T05:30:00.000Z"}) == (TUE, 6.5)
    assert pack_now({"today": "2026-11-24"}) == (TUE, 6.5)


def test_rules_only_when_switch_on(monkeypatch):
    monkeypatch.delenv("TEAM_ORDER_RULES", raising=False)
    assert ro.order_rules_section() == ""
    monkeypatch.setenv("TEAM_ORDER_RULES", "1")
    assert "ten sacks" in ro.order_rules_section()


# ── T3 / T4: review before confirm_order ──

PRODUCTS = {
    "prd_0001": {"id": "prd_0001", "name": "Traditional T55 flour (sack 25 kg)", "unit": "piece", "caliber": "25 kg sack"},
    "prd_0025": {"id": "prd_0025", "name": "Butter AOP Charentes-Poitou 84% (2 kg slab)", "unit": "kg", "caliber": "box of 5 slabs of 2 kg"},
    "prd_0011": {"id": "prd_0011", "name": "Fresh baker's yeast (500 g block)", "unit": "piece", "caliber": "500 g block"},
    "prd_0034": {"id": "prd_0034", "name": "Free-range medium eggs (plate of 30)", "unit": "box", "caliber": "tray 30"},
}


def line(pid, qty, available=100.0):
    p = PRODUCTS[pid]
    return {"productId": pid, "qty": qty, "unit": p["unit"], "productName": p["name"], "available": available}


def test_say_quantity():
    assert ro.say_quantity(12, "piece", "25 kg sack") == "12 sacks"
    assert ro.say_quantity(1, "piece", "25 kg sack") == "1 sack"
    assert ro.say_quantity(40, "kg") == "40 kilos"
    assert ro.say_quantity(1.5, "liter", "brick 1 L") == "1.5 litres"
    assert ro.say_quantity(4, "box", "tray 30") == "4 trays"


def test_review_readback_and_franco():
    order = {"id": "ord_1", "deliveryDate": "2026-11-26", "totalHt": 41.4, "warnings": [],
             "lines": [line("prd_0001", 2), line("prd_0011", 1)]}
    r = ro.review(order, PRODUCTS, [])
    assert r["readback"] == ("2 sacks of Traditional T55 flour, 1 block of Fresh baker's yeast, "
                             "for delivery on Thursday 26 November")
    assert r["canConfirm"] is True and r["alerts"] == [] and r["askFirst"] == []
    assert "12 euros" in r["franco"] and "109" in r["franco"]
    big = {**order, "totalHt": 189.0}
    assert "franco" not in ro.review(big, PRODUCTS, [])


def test_review_translates_erp_warnings():
    order = {"id": "ord_2", "deliveryDate": "2026-11-25", "totalHt": 495.6,
             "lines": [line("prd_0025", 40, available=0), line("prd_0001", 2)],
             "warnings": [
                 {"code": "client_blocked", "message": "The client Le Pétrin de Balma is blocked"},
                 {"code": "credit_limit", "message": "Credit ceiling exceeded: outstanding € 9,465.37 ..."},
                 {"code": "insufficient_stock", "productId": "prd_0025", "message": "Insufficient stock ..."},
                 {"code": "price_below_cost", "productId": "prd_0001", "message": "sold under the cost"},
             ]}
    r = ro.review(order, PRODUCTS, [])
    assert r["canConfirm"] is False
    assert r["blockedBy"] == ["client_blocked", "credit_limit", "insufficient_stock"]
    said = " ".join(r["alerts"])
    assert "blocked" in said and "credit limit" in said and "out of stock" in said
    assert "9 465" not in said and "Cost" not in said  # no internal figures, no margin talk


def test_review_partial_stock_says_what_is_left():
    order = {"id": "ord_3", "deliveryDate": "2026-11-26", "totalHt": 300, "lines": [line("prd_0034", 20, available=6)],
             "warnings": [{"code": "insufficient_stock", "productId": "prd_0034"}]}
    assert ro.review(order, PRODUCTS, [])["alerts"] == ["Free-range medium eggs: only 6 trays left"]


def test_unusual_quantity_is_asked_first():
    usual = [{"productId": "prd_0001", "avgQty": 17.9}, {"productId": "prd_0011", "avgQty": 0}]
    order = {"id": "ord_4", "deliveryDate": "2026-11-26", "totalHt": 3960, "warnings": [],
             "lines": [line("prd_0001", 200), line("prd_0011", 30)]}
    r = ro.review(order, PRODUCTS, usual)
    assert r["askFirst"] == ["200 sacks of Traditional T55 flour, compared with your usual 17.9 sacks"]
    assert r["canConfirm"] is True  # asking is enough: the caller may really want it
    normal = {**order, "lines": [line("prd_0001", 20)]}
    assert ro.review(normal, PRODUCTS, usual)["askFirst"] == []


# ── Garde-fou doublons (S05 / S31) ──


def test_voice_drafts_left_behind_are_duplicates_other_channels_are_not():
    me = {"id": "ord_new", "deliveryDate": "2026-11-25", "totalHt": 276, "warnings": [], "lines": [line("prd_0001", 10)]}
    client_orders = [
        {"id": "ord_new", "status": "draft", "source": "voice_agent", "deliveryDate": "2026-11-25"},  # itself
        {"id": "ord_old", "number": "CMD-1", "status": "draft", "source": "voice_agent", "deliveryDate": "2026-11-25"},
        {"id": "ord_wa", "number": "CMD-2", "status": "draft", "source": "whatsapp", "deliveryDate": "2026-11-25"},
        {"id": "ord_other_day", "status": "confirmed", "source": "phone", "deliveryDate": "2026-11-28"},
        {"id": "ord_gone", "status": "cancelled", "source": "voice_agent", "deliveryDate": "2026-11-25"},
    ]
    r = ro.review(me, PRODUCTS, [], client_orders)
    assert [d["orderId"] for d in r["duplicateDrafts"]] == ["ord_old"]
    assert [d["orderId"] for d in r["sameDayOrders"]] == ["ord_wa"]  # a WhatsApp draft is mentioned, never cancelled


def test_no_other_orders_no_extra_keys():
    me = {"id": "ord_new", "deliveryDate": "2026-11-25", "totalHt": 276, "warnings": [], "lines": [line("prd_0001", 10)]}
    r = ro.review(me, PRODUCTS, [], [{"id": "ord_new", "status": "draft", "source": "voice_agent"}])
    assert "duplicateDrafts" not in r and "sameDayOrders" not in r


def test_rules_say_erp_days_win_over_closed_notes(monkeypatch):
    monkeypatch.setenv("TEAM_ORDER_RULES", "1")
    rules = ro.order_rules_section()
    assert "Closed on" in rules and "Use ERP delivery days" in rules
    assert "duplicateDrafts" in rules and "cancel_draft_order" in rules


def test_duplicate_draft_detail_says_if_it_is_the_same_order():
    me = {"id": "ord_new", "deliveryDate": "2026-11-26", "totalHt": 189, "warnings": [], "lines": [line("prd_0001", 10)]}
    same = {"id": "ord_a", "status": "draft", "source": "voice_agent", "deliveryDate": "2026-11-26", "lines": [line("prd_0001", 10)]}
    other = {"id": "ord_b", "status": "draft", "source": "voice_agent", "deliveryDate": "2026-11-26",
             "lines": [line("prd_0001", 200), line("prd_0011", 3)]}
    dups = {d["orderId"]: d for d in ro.review(me, PRODUCTS, [], [same, other])["duplicateDrafts"]}
    assert dups["ord_a"]["sameAsThis"] is True
    assert dups["ord_b"]["sameAsThis"] is False
    assert dups["ord_b"]["readback"] == "200 sacks of Traditional T55 flour, 3 blocks of Fresh baker's yeast"


# - - Prices spoken (recording) S05 "92 euros the plate... pardon, 18 euros 40") - -

TOURAGE = ("kg", "box of 5 slabs of 2 kg", "Touring butter 82 % (2 kg slab)")
CREME = ("liter", "6 × 1 L carton", "Liquid cream UHT 35 % (Brick 1 L)")


def test_fr_money():
    assert ro.fr_money(9.2) == "9 euros and 20 cents"
    assert ro.fr_money(92) == "92 euros"
    assert ro.fr_money(1.05) == "1 euro and 5 cents"
    assert ro.fr_money(0.5) == "50 cents"


def test_packaging_of_weighed_and_liquid_products():
    assert ro.packaging(*TOURAGE) == [("box", 10), ("slab", 2)]
    assert ro.packaging("kg", "1 kg block", "Sweet butter AOP (carton 10 × 1 kg)") == [("carton", 10), ("block", 1)]
    assert ro.packaging(*CREME) == [("carton", 6), ("brick", 1)]
    assert ro.packaging("kg", "carton 12,5 kg", "Sultanine dried grapes (carton 12.5 kg)") == [("carton", 12.5)]
    assert ro.packaging("piece", "25 kg sack", "Flour (sack 25 kg)") == []


def test_said_packages_become_selling_units():
    assert ro.to_selling_qty(3, "boxes", *TOURAGE) == 30
    assert ro.to_selling_qty(4, "slabs", *TOURAGE) == 8
    assert ro.to_selling_qty(40, "kilos", *TOURAGE) == 40
    assert ro.to_selling_qty(2, "cartons", *CREME) == 12
    assert ro.to_selling_qty(50, "kg", "piece", "25 kg sack", "Flour (sack 25 kg)") == 2


def test_quote_the_s05_case():
    q = ro.quote(3, *TOURAGE, unit_price=9.2, said_unit="boxes")
    assert q["say"] == "9 euros and 20 cents per kilo, 92 euros per 10-kilo box, 18 euros and 40 cents per 2-kilo slab"
    assert q["total"] == "276 euros excluding VAT for 30 kilos, or 3 boxes"
    assert q["totalHt"] == 276


def test_quote_other_units():
    assert ro.quote(20, *CREME, unit_price=4.1)["say"] == "4 euros and 10 cents per litre, 24 euros and 60 cents per 6-litre carton"
    flour = ro.quote(10, "piece", "25 kg sack", "Flour (sack 25 kg)", 18.9)
    assert flour["say"] == "18 euros and 90 cents per 25 kg sack" and flour["total"] == "189 euros excluding VAT for 10 sacks"
    assert ro.quote(2, "piece", "500 g block", "Yeast (500 g block)", 1.35)["say"] == "1 euro and 35 cents per 500 g block"


# "Jev: "Is it a true yes?" (lines calibrated on 12 real answers) - "


def test_classify_answer_from_calibration():
    assert ro.classify_answer(0.96, 0.14) == "yes"  # « Oui c'est bon. »
    assert ro.classify_answer(0.89, 0.22) == "yes"  # « Bon d'accord. »
    assert ro.classify_answer(0.03, 0.91) == "change"  # « Oui mais mettez-en quatre. »
    assert ro.classify_answer(0.12, 0.93) == "change"  # "How many are they already?"
    assert ro.classify_answer(0.02, 0.20) == "no"  # « Non, laissez tomber. »
    assert ro.classify_answer(0.55, 0.40) == "unsure"
    assert ro.classify_answer(0.85, 0.70) == "unsure"  # yes AND a change: ask again
    assert ro.classify_answer(0.95, 0.55) == "yes"  # « C'est bon, validez » after a price question (seen live)


class FakeErp:
    def __init__(self, order):
        self.order, self.posted = order, []

    async def get(self, path, query=None):
        return self.order

    async def post(self, path, body=None):
        self.posted.append(path)
        return {**self.order, "status": "confirmed"}


class FakeJev:
    def __init__(self, accord, change):
        self.answers = {"accord": {"noul": accord}, "change": {"noul": change}}

    async def ask(self, state, questions):
        return {"answers": self.answers}


def jev_confirm():
    """The Jev-guarded confirm_order, without leaving the kit's tool replaced for the other tests."""
    import importlib

    from app.tools import registry

    saved = dict(registry.TOOLS)
    from app.tools import order_jev

    registry.TOOLS.pop("resolve_product", None)  # the reload registers it again
    importlib.reload(order_jev)  # pops whichever confirm_order is there and registers the Jev one
    fn = registry.TOOLS["confirm_order"].fn
    registry.TOOLS.clear()
    registry.TOOLS.update(saved)
    return fn


ORDER = {"id": "ord_1", "number": "CMD-1", "status": "draft", "clientId": "cli_0001", "deliveryDate": "2026-11-26",
         "totalHt": 189, "warnings": [], "lines": [{"id": "l1", "productId": "prd_0001", "qty": 10}]}


def run(coro):
    import asyncio

    return asyncio.run(coro)


def test_confirm_only_on_a_real_yes(monkeypatch):
    import app.clients as clients
    from app.tools.registry import ToolContext

    confirm = jev_confirm()
    for accord, change, confirmed in [(0.96, 0.14, True), (0.03, 0.91, False), (0.5, 0.4, False)]:
        erp = FakeErp(ORDER)
        monkeypatch.setattr(clients, "get_jev_client", lambda a=accord, c=change: FakeJev(a, c))
        r = run(confirm(ToolContext(erp=erp, actor="voice_agent"), "ord_1", "answer", "Do I have a valid date?"))
        assert r["confirmed"] is confirmed and r["decidedBy"] == "jev"
        assert erp.posted == (["/api/orders/ord_1/confirm"] if confirmed else [])
        if not confirmed:
            assert r["next"]


def test_confirm_blocked_by_erp_warning_and_fallback_without_jev(monkeypatch):
    import app.clients as clients
    from app.tools.registry import ToolContext

    confirm = jev_confirm()
    blocked = FakeErp({**ORDER, "warnings": [{"code": "client_blocked"}]})
    r = run(confirm(ToolContext(erp=blocked, actor="voice_agent"), "ord_1", "yes", None))
    assert r["confirmed"] is False and r["blockedBy"] == ["client_blocked"] and blocked.posted == []
    monkeypatch.setattr(clients, "get_jev_client", lambda: None)  # no key: the kit's behaviour
    erp = FakeErp(ORDER)
    r = run(confirm(ToolContext(erp=erp, actor="voice_agent"), "ord_1", "yes", None))
    assert r["confirmed"] is True and r["decidedBy"] == "agent"


def test_alias_match_settles_exact_names_but_never_glossary_ambiguous_words():
    cat = {
        "prd_0011": {"name": "Fresh baker's yeast (500 g block)", "aliases": ["levure", "yeast block", "fresh yeast"]},
        "prd_0012": {"name": "Instant dry yeast (pack 500 g)", "aliases": ["dry yeast", "dry"]},
        "prd_0001": {"name": "Traditional T55 flour (sack 25 kg)", "aliases": ["tradi", "tradition"]},
        "prd_0025": {"name": "Butter AOP 84 % (2 kg slab)", "aliases": ["AOP laminating butter", "laminating butter"]},
        "prd_0026": {"name": "Touring butter 82 % (2 kg slab)", "aliases": ["tourage standard", "laminating butter"]},
        "prd_0046": {"name": "White almond powder (sac 5 kg)", "aliases": ["almond powder", "poudre"]},
        "prd_0099": {"name": "Former product", "aliases": ["discontinued"], "active": False},
    }
    assert ro.alias_match("Yeast blocks", cat) == "prd_0011"
    assert ro.alias_match("Dry yeast", cat) == "prd_0012"
    assert ro.alias_match("tradition", cat) == "prd_0001"
    assert ro.alias_match("AOP laminating butter", cat) == "prd_0025"
    assert ro.alias_match("laminating butter", cat) is None  # glossary: always clarify
    assert ro.alias_match("Powder", cat) is None  # glossary: always clarify, even if one alias matches
    assert ro.alias_match("discontinued", cat) is None  # inactive
    assert ro.alias_match("Bread", cat) is None  # no exact alias: search + Jev
    salted = {"prd_0029": {"name": "Half-salt butter (motte 1 kg)", "aliases": ["lightly salted butter", "salted butter"]}}
    assert ro.alias_match("the lightly salted butter", salted) == "prd_0029"  # the article goes, not the "de" of « demi »
