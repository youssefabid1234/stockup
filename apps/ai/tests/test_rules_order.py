"""Team 12 · Amine Khalil · deterministic helpers of agent/rules_order.py (dates of delivery, units)."""

from datetime import date

from app.agent import rules_order as ro
from app.tools.delivery import pack_now

TUE = date(2026, 11, 24)  # business date of the pack, 06h30
SARRAILH = ["tue", "thu", "sat"]
LAURAGAIS = ["tue", "fri"]


def test_weekday_names_and_relative_days():
    assert ro.next_delivery_date(TUE, SARRAILH, "jeudi") == date(2026, 11, 26)
    assert ro.next_delivery_date(TUE, SARRAILH, "Jeudi prochain") == date(2026, 11, 26)
    assert ro.next_delivery_date(TUE, SARRAILH, "samedi") == date(2026, 11, 28)
    assert ro.next_delivery_date(TUE, SARRAILH, "après-demain") == date(2026, 11, 26)
    assert ro.next_delivery_date(TUE, SARRAILH, "mardi") == date(2026, 12, 1)  # said on a Tuesday = next Tuesday
    assert ro.next_delivery_date(TUE, SARRAILH, "le 28") == date(2026, 11, 28)
    assert ro.next_delivery_date(TUE, SARRAILH, "26/11") == date(2026, 11, 26)


def test_day_not_delivered_or_gone():
    assert ro.next_delivery_date(TUE, SARRAILH, "mercredi") is None
    assert ro.next_delivery_date(TUE, SARRAILH, "demain") is None  # Wednesday
    assert ro.next_delivery_date(TUE, SARRAILH, "aujourd'hui") is None  # routes left at 06h30
    assert ro.next_delivery_date(TUE, SARRAILH, "n'importe quand ce truc") is None


def test_asap_is_first_possible_day():
    assert ro.next_delivery_date(TUE, SARRAILH, "au plus vite") == date(2026, 11, 26)
    assert ro.next_delivery_date(TUE, SARRAILH, None) == date(2026, 11, 26)
    assert ro.next_delivery_date(TUE, ["mon", "wed", "fri"], "dès que possible") == date(2026, 11, 25)
    assert ro.next_delivery_date(TUE, [], None) is None


def test_cutoffs():
    wed_clients = ["mon", "wed", "fri"]
    assert ro.next_delivery_date(TUE, wed_clients, "demain", now_hour=16.9) == date(2026, 11, 25)
    assert ro.next_delivery_date(TUE, wed_clients, "demain", now_hour=17) is None  # after 17h: too late for tomorrow
    assert ro.next_delivery_date(TUE, wed_clients, None, now_hour=18) == date(2026, 11, 27)
    # Lauragais-Tarn: order the day before before noon; Friday is still fine on Tuesday
    assert ro.next_delivery_date(TUE, LAURAGAIS, "vendredi", cutoff_hour=12) == date(2026, 11, 27)
    thu = date(2026, 11, 26)
    assert ro.next_delivery_date(thu, LAURAGAIS, "vendredi", now_hour=11, cutoff_hour=12) == date(2026, 11, 27)
    assert ro.next_delivery_date(thu, LAURAGAIS, "vendredi", now_hour=13, cutoff_hour=12) is None


def test_delivery_answer_for_the_agent():
    ok = ro.delivery_answer(TUE, SARRAILH, "jeudi", 6.5)
    assert ok == {"deliveryDays": ["mardi", "jeudi", "samedi"], "ok": True, "date": "2026-11-26", "say": "jeudi 26 novembre"}
    no = ro.delivery_answer(TUE, SARRAILH, "mercredi", 6.5)
    assert no["ok"] is False and "mercredi" in no["reason"]
    assert no["nextPossible"] == "2026-11-26" and no["sayNext"] == "jeudi 26 novembre"
    gone = ro.delivery_answer(TUE, LAURAGAIS, "ce matin", 6.5, zone="Lauragais & Tarn")
    assert gone["ok"] is False and "dépôt" in gone["reason"] and gone["nextPossible"] == "2026-11-27"
    late = ro.delivery_answer(date(2026, 11, 26), LAURAGAIS, "vendredi", 14, zone="Lauragais & Tarn")
    assert late["ok"] is False and "12h" in late["reason"] and late["nextPossible"] == "2026-12-01"


def test_units():
    assert ro.sacks_from_words("sac 25 kg", 10, None) == 10  # « 10 de tradi »
    assert ro.sacks_from_words("sac 25 kg", 10, "sacs") == 10
    assert ro.sacks_from_words("sac 25 kg", 50, "kilos") == 2
    assert ro.sacks_from_words("sac 10 kg", 30, "kg") == 3  # épeautre
    assert ro.sacks_from_words("sac 25 kg", 40, "kg") == 1.6  # not a whole sack: the agent asks
    assert ro.sacks_from_words("kg", 40, "kilos") == 40  # tourage is sold by the kilo
    assert ro.sacks_from_words("carton 140", 4, None) == 4


def test_pack_now_reads_the_pack_clock():
    assert pack_now({"today": "2026-11-24", "generatedAt": "2026-11-24T05:30:00.000Z"}) == (TUE, 6.5)
    assert pack_now({"today": "2026-11-24"}) == (TUE, 6.5)


def test_rules_only_when_switch_on(monkeypatch):
    monkeypatch.delenv("TEAM_ORDER_RULES", raising=False)
    assert ro.order_rules_section() == ""
    monkeypatch.setenv("TEAM_ORDER_RULES", "1")
    assert "10 de tradi" in ro.order_rules_section()


# ── T3 / T4: review before confirm_order ──

PRODUCTS = {
    "prd_0001": {"id": "prd_0001", "name": "Farine de blé T55 tradition française (sac 25 kg)", "unit": "piece", "caliber": "sac 25 kg"},
    "prd_0025": {"id": "prd_0025", "name": "Beurre de tourage AOP Charentes-Poitou 84 % (plaque 2 kg)", "unit": "kg", "caliber": "carton 5 plaques de 2 kg"},
    "prd_0011": {"id": "prd_0011", "name": "Levure fraîche boulangère (pain de 500 g)", "unit": "piece", "caliber": "pain 500 g"},
    "prd_0034": {"id": "prd_0034", "name": "Œufs plein air calibre M (plateau de 30)", "unit": "box", "caliber": "plateau 30"},
}


def line(pid, qty, available=100.0):
    p = PRODUCTS[pid]
    return {"productId": pid, "qty": qty, "unit": p["unit"], "productName": p["name"], "available": available}


def test_say_quantity():
    assert ro.say_quantity(12, "piece", "sac 25 kg") == "12 sacs"
    assert ro.say_quantity(1, "piece", "sac 25 kg") == "1 sac"
    assert ro.say_quantity(40, "kg") == "40 kilos"
    assert ro.say_quantity(1.5, "liter", "brique 1 L") == "1,5 litres"
    assert ro.say_quantity(4, "box", "plateau 30") == "4 plateaux"


def test_review_readback_and_franco():
    order = {"id": "ord_1", "deliveryDate": "2026-11-26", "totalHt": 41.4, "warnings": [],
             "lines": [line("prd_0001", 2), line("prd_0011", 1)]}
    r = ro.review(order, PRODUCTS, [])
    assert r["readback"] == ("2 sacs de Farine de blé T55 tradition française, 1 pain de Levure fraîche boulangère ; "
                             "livraison jeudi 26 novembre")
    assert r["canConfirm"] is True and r["alerts"] == [] and r["askFirst"] == []
    assert "12 euros" in r["franco"] and "109" in r["franco"]
    big = {**order, "totalHt": 189.0}
    assert "franco" not in ro.review(big, PRODUCTS, [])


def test_review_translates_erp_warnings():
    order = {"id": "ord_2", "deliveryDate": "2026-11-25", "totalHt": 495.6,
             "lines": [line("prd_0025", 40, available=0), line("prd_0001", 2)],
             "warnings": [
                 {"code": "client_blocked", "message": "Le client Le Pétrin de Balma est bloqué"},
                 {"code": "credit_limit", "message": "Plafond de crédit dépassé : encours 9 465,37 € …"},
                 {"code": "insufficient_stock", "productId": "prd_0025", "message": "Stock insuffisant …"},
                 {"code": "price_below_cost", "productId": "prd_0001", "message": "vendu sous le coût"},
             ]}
    r = ro.review(order, PRODUCTS, [])
    assert r["canConfirm"] is False
    assert r["blockedBy"] == ["client_blocked", "credit_limit", "insufficient_stock"]
    said = " ".join(r["alerts"])
    assert "bloqué" in said and "plafond" in said and "en rupture" in said
    assert "9 465" not in said and "coût" not in said  # no internal figures, no margin talk


def test_review_partial_stock_says_what_is_left():
    order = {"id": "ord_3", "deliveryDate": "2026-11-26", "totalHt": 300, "lines": [line("prd_0034", 20, available=6)],
             "warnings": [{"code": "insufficient_stock", "productId": "prd_0034"}]}
    assert ro.review(order, PRODUCTS, [])["alerts"] == ["Œufs plein air calibre M : il n'en reste que 6 plateaux"]


def test_unusual_quantity_is_asked_first():
    usual = [{"productId": "prd_0001", "avgQty": 17.9}, {"productId": "prd_0011", "avgQty": 0}]
    order = {"id": "ord_4", "deliveryDate": "2026-11-26", "totalHt": 3960, "warnings": [],
             "lines": [line("prd_0001", 200), line("prd_0011", 30)]}
    r = ro.review(order, PRODUCTS, usual)
    assert r["askFirst"] == ["200 sacs de Farine de blé T55 tradition française, alors que d'habitude c'est environ 17,9 sacs"]
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
    assert "Fermé le" in rules and "font foi" in rules
    assert "duplicateDrafts" in rules and "cancel_draft_order" in rules


def test_duplicate_draft_detail_says_if_it_is_the_same_order():
    me = {"id": "ord_new", "deliveryDate": "2026-11-26", "totalHt": 189, "warnings": [], "lines": [line("prd_0001", 10)]}
    same = {"id": "ord_a", "status": "draft", "source": "voice_agent", "deliveryDate": "2026-11-26", "lines": [line("prd_0001", 10)]}
    other = {"id": "ord_b", "status": "draft", "source": "voice_agent", "deliveryDate": "2026-11-26",
             "lines": [line("prd_0001", 200), line("prd_0011", 3)]}
    dups = {d["orderId"]: d for d in ro.review(me, PRODUCTS, [], [same, other])["duplicateDrafts"]}
    assert dups["ord_a"]["sameAsThis"] is True
    assert dups["ord_b"]["sameAsThis"] is False
    assert dups["ord_b"]["readback"] == "200 sacs de Farine de blé T55 tradition française, 3 pains de Levure fraîche boulangère"


# ── Prix dits à l'oral (enregistrement S05 : « 92 euros la plaque… pardon, 18 euros 40 ») ──

TOURAGE = ("kg", "carton 5 plaques de 2 kg", "Beurre de tourage 82 % (plaque 2 kg)")
CREME = ("liter", "carton 6 × 1 L", "Crème liquide UHT 35 % (brique 1 L)")


def test_fr_money():
    assert ro.fr_money(9.2) == "9 euros 20"
    assert ro.fr_money(92) == "92 euros"
    assert ro.fr_money(1.05) == "1 euro 05"
    assert ro.fr_money(0.5) == "50 centimes"


def test_packaging_of_weighed_and_liquid_products():
    assert ro.packaging(*TOURAGE) == [("carton", 10), ("plaque", 2)]
    assert ro.packaging("kg", "plaquette 1 kg", "Beurre doux AOP (carton 10 × 1 kg)") == [("carton", 10), ("plaquette", 1)]
    assert ro.packaging(*CREME) == [("carton", 6), ("brique", 1)]
    assert ro.packaging("kg", "carton 12,5 kg", "Raisins secs sultanines (carton 12,5 kg)") == [("carton", 12.5)]
    assert ro.packaging("piece", "sac 25 kg", "Farine (sac 25 kg)") == []


def test_said_packages_become_selling_units():
    assert ro.to_selling_qty(3, "cartons", *TOURAGE) == 30
    assert ro.to_selling_qty(4, "plaques", *TOURAGE) == 8
    assert ro.to_selling_qty(40, "kilos", *TOURAGE) == 40
    assert ro.to_selling_qty(2, "cartons", *CREME) == 12
    assert ro.to_selling_qty(50, "kg", "piece", "sac 25 kg", "Farine (sac 25 kg)") == 2


def test_quote_the_s05_case():
    q = ro.quote(3, *TOURAGE, unit_price=9.2, said_unit="cartons")
    assert q["say"] == "9 euros 20 le kilo, soit 92 euros le carton de 10 kilos (18 euros 40 la plaque de 2 kilos)"
    assert q["total"] == "276 euros hors taxes pour 30 kilos, soit 3 cartons"
    assert q["totalHt"] == 276


def test_quote_other_units():
    assert ro.quote(20, *CREME, unit_price=4.1)["say"] == "4 euros 10 le litre, soit 24 euros 60 le carton de 6 litres"
    flour = ro.quote(10, "piece", "sac 25 kg", "Farine (sac 25 kg)", 18.9)
    assert flour["say"] == "18 euros 90 le sac de 25 kilos" and flour["total"] == "189 euros hors taxes pour 10 sacs"
    assert ro.quote(2, "piece", "pain 500 g", "Levure (pain de 500 g)", 1.35)["say"] == "1 euro 35 le pain de 500 grammes"


# ── Jev : « est-ce un vrai oui ? » (seuils calibrés sur 12 vraies réponses) ──


def test_classify_answer_from_calibration():
    assert ro.classify_answer(0.96, 0.14) == "yes"  # « Oui c'est bon. »
    assert ro.classify_answer(0.89, 0.22) == "yes"  # « Bon d'accord. »
    assert ro.classify_answer(0.03, 0.91) == "change"  # « Oui mais mettez-en quatre. »
    assert ro.classify_answer(0.12, 0.93) == "change"  # « C'est combien déjà ? »
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
        r = run(confirm(ToolContext(erp=erp, actor="voice_agent"), "ord_1", "réponse", "Je valide ?"))
        assert r["confirmed"] is confirmed and r["decidedBy"] == "jev"
        assert erp.posted == (["/api/orders/ord_1/confirm"] if confirmed else [])
        if not confirmed:
            assert r["next"]


def test_confirm_blocked_by_erp_warning_and_fallback_without_jev(monkeypatch):
    import app.clients as clients
    from app.tools.registry import ToolContext

    confirm = jev_confirm()
    blocked = FakeErp({**ORDER, "warnings": [{"code": "client_blocked"}]})
    r = run(confirm(ToolContext(erp=blocked, actor="voice_agent"), "ord_1", "oui", None))
    assert r["confirmed"] is False and r["blockedBy"] == ["client_blocked"] and blocked.posted == []
    monkeypatch.setattr(clients, "get_jev_client", lambda: None)  # no key: the kit's behaviour
    erp = FakeErp(ORDER)
    r = run(confirm(ToolContext(erp=erp, actor="voice_agent"), "ord_1", "oui", None))
    assert r["confirmed"] is True and r["decidedBy"] == "agent"


def test_alias_match_settles_exact_names_but_never_glossary_ambiguous_words():
    cat = {
        "prd_0011": {"name": "Levure fraîche boulangère (pain de 500 g)", "aliases": ["levure", "pain de levure", "levure fraîche"]},
        "prd_0012": {"name": "Levure sèche instantanée (paquet 500 g)", "aliases": ["levure sèche", "sèche"]},
        "prd_0001": {"name": "Farine de blé T55 tradition française (sac 25 kg)", "aliases": ["tradi", "la tradition"]},
        "prd_0025": {"name": "Beurre de tourage AOP 84 % (plaque 2 kg)", "aliases": ["tourage AOP", "tourage"]},
        "prd_0026": {"name": "Beurre de tourage 82 % (plaque 2 kg)", "aliases": ["tourage standard", "tourage"]},
        "prd_0046": {"name": "Poudre d'amande blanche (sac 5 kg)", "aliases": ["poudre d'amande", "poudre"]},
        "prd_0099": {"name": "Ancien produit", "aliases": ["vieux"], "active": False},
    }
    assert ro.alias_match("pains de levure", cat) == "prd_0011"
    assert ro.alias_match("de la levure sèche", cat) == "prd_0012"
    assert ro.alias_match("la tradition", cat) == "prd_0001"
    assert ro.alias_match("du tourage AOP", cat) == "prd_0025"
    assert ro.alias_match("tourage", cat) is None  # glossary: always clarify
    assert ro.alias_match("de la poudre", cat) is None  # glossary: always clarify, even if one alias matches
    assert ro.alias_match("vieux", cat) is None  # inactive
    assert ro.alias_match("du pain", cat) is None  # no exact alias: search + Jev
    salted = {"prd_0029": {"name": "Beurre demi-sel de baratte (motte 1 kg)", "aliases": ["demi-sel", "beurre salé"]}}
    assert ro.alias_match("du demi-sel", salted) == "prd_0029"  # the article goes, not the "de" of « demi »
