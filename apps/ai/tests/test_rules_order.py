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
