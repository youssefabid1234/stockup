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
