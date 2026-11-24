"""Youssef · a new client on the phone becomes a real prospect in the ERP: no duplicate, right type/zone, request saved."""

import pytest

from app.agent.call_context import NEW_CLIENT_RULES
from app.tools import TOOLS
from app.tools import new_client as nc
from app.tools.registry import ToolContext

CLIENTS = [
    {"id": "cli_0001", "name": "Maison Sarrailh", "status": "active", "city": "Toulouse", "zone": "Toulouse centre & faubourgs",
     "contacts": [{"name": "Nadine Sarrailh", "phone": "05 61 21 33 47"}]},
    {"id": "cli_0050", "name": "Le Fournil de Blagnac", "status": "blocked", "city": "Blagnac", "zone": "Blagnac, Colomiers & Ouest",
     "contacts": [{"name": "Paul", "phone": "06 11 22 33 44"}]},
    {"id": "cli_0060", "name": "Pains de Colomiers", "status": "active", "city": "Colomiers", "zone": "Blagnac, Colomiers & Ouest",
     "contacts": []},
    {"id": "cli_0070", "name": "Boulangerie du Canal", "status": "prospect", "city": None, "zone": None,
     "contacts": [{"name": "Camille", "phone": "07 99 99 99 99"}]},
]  # fmt: skip
ROUTES = [
    {"id": "rte_0001", "zone": "Toulouse centre & faubourgs", "days": ["mon", "tue", "wed", "thu", "fri", "sat"]},
    {"id": "rte_0003", "zone": "Blagnac, Colomiers & Ouest", "days": ["mon", "tue", "wed", "thu", "fri"]},
]


CONTEXT = [
    {"title": "Zone Toulouse centre & faubourgs", "body": "Communes / quartiers : Toulouse (Capitole) (31000), Toulouse (Saint-Cyprien) (31300). Livrée lundi."},
    {"title": "Zone Fondeyre, L'Union & Nord toulousain", "body": "Communes / quartiers : Toulouse (Minimes) (31200), L'Union (31240), Saint-Jean (31240). Livrée lundi."},
    {"title": "Zone Blagnac, Colomiers & Ouest", "body": "Communes / quartiers : Blagnac (31700), Colomiers (31770), Tournefeuille (31170). Livrée lundi."},
    {"title": "Chiffres clés", "body": "104 clients"},
]  # fmt: skip


class FakeErp:
    def __init__(self):
        self.posts, self.patches = [], []

    async def get(self, path, params=None):
        if path == "/api/context/for":
            return {"entries": []}
        if path == "/api/clients/cli_0070":
            return {**CLIENTS[3], "address": "12 quai du Canal", "city": "Toulouse", "deliveryDays": [], "usual": [], "notes": []}
        if path.endswith("/events"):
            return [{"type": "onboarding", "description": "10 sacs de tradi pour jeudi · contact : Camille · tél. 07 99 99 99 99"}]
        return {"/api/clients": CLIENTS, "/api/routes": ROUTES, "/api/context": CONTEXT}[path]

    async def post(self, path, body=None):
        self.posts.append((path, body))
        return {"id": "cli_0105", **body} if path == "/api/clients" else {"id": "evt_1", **body}

    async def patch(self, path, body=None):
        self.patches.append((path, body))
        return body


@pytest.fixture(autouse=True)
def fresh():
    nc.clear_cache()
    yield
    nc.clear_cache()


def ctx(erp):
    return ToolContext(erp=erp, actor="voice_agent")


async def register(erp, **args):
    """As the model calls it: arguments validated by the tool's own model (defaults applied)."""
    return await nc.register_new_client.run(args, ctx(erp))


async def test_creates_a_prospect_with_type_zone_days_and_saves_the_request():
    erp = FakeErp()
    out = await register(erp, company_name="Le Grain d'Or", city="colomiers", request="10 sacs de tradi pour jeudi",
        contact_name="Camille Durand", phone="+33 6 12 34 56 78", address="3 rue des Lilas", kind="Boulangerie",
    )  # fmt: skip
    (p1, client), (p2, event) = erp.posts
    assert p1 == "/api/clients" and client["status"] == "prospect" and client["type"] == "fishmonger"
    assert client["tags"] == ["boulangeries"] and client["zone"] == "Blagnac, Colomiers & Ouest"
    assert client["deliveryDays"] == ["mon", "tue", "wed", "thu", "fri"] and client["contacts"][0]["phone"] == "+33 6 12 34 56 78"
    assert p2 == "/api/clients/cli_0105/events" and event["type"] == "onboarding" and "10 sacs de tradi" in event["description"]
    assert out["created"] and out["clientId"] == "cli_0105" and "aucune commande" in out["next"]
    assert out["deliveryDays"] == ["lundi", "mardi", "mercredi", "jeudi", "vendredi"]


async def test_same_phone_as_an_active_client_is_not_a_new_client():
    erp = FakeErp()
    out = await register(erp, company_name="Autre nom", city="Toulouse", request="un devis", phone="0561213347")
    assert out["existing"] and out["clientId"] == "cli_0001" and erp.posts == []


async def test_blocked_client_by_name_is_reported_blocked():
    out = await register(FakeErp(), company_name="le fournil de BLAGNAC", city="Blagnac", request="farine")
    assert out["existing"] and out["status"] == "blocked" and "BLOQUÉ" in out["next"]


async def test_a_second_call_completes_the_same_prospect():
    erp = FakeErp()
    out = await register(erp, company_name="Boulangerie du Canal", city="Toulouse", request="et aussi du beurre", phone="07 99 99 99 99",
        address="12 quai du Canal",
    )  # fmt: skip
    assert not out["created"] and out["clientId"] == "cli_0070"
    assert erp.patches == [("/api/clients/cli_0070", {"address": "12 quai du Canal", "city": "Toulouse", "zone": "Toulouse centre & faubourgs",
                                                    "deliveryDays": ["mon", "tue", "wed", "thu", "fri", "sat"]})]
    assert [p for p, _ in erp.posts] == ["/api/clients/cli_0070/events"]


async def test_out_of_zone_city_is_said_honestly():
    erp = FakeErp()
    out = await register(erp, company_name="Chez Lulu", city="Montpellier", request="pain", kind="restaurant")
    assert out["outOfZone"] and "aucune de nos zones" in out["next"] and erp.posts[0][1]["type"] == "restaurant"


def test_kinds_and_registration():
    assert nc.kind_of("pâtisserie-salon de thé") == ("fishmonger", ["patisseries"])
    assert nc.kind_of("Hôtel") == ("hotel", []) and nc.kind_of(None) == ("fishmonger", ["boulangeries"])
    assert "register_new_client" in TOOLS and "register_new_client" in NEW_CLIENT_RULES


async def test_zone_from_the_erp_zone_sheets_quartier_postal_code_or_city():
    d = await nc._directory(FakeErp())
    assert nc.zone_for(d, "Tournefeuille")[0] == "Blagnac, Colomiers & Ouest"  # no client there: the zone sheet knows it
    assert nc.zone_for(d, "Toulouse, quartier des Minimes")[0] == "Fondeyre, L'Union & Nord toulousain"
    assert nc.zone_for(d, "toulouse")[0] == "Toulouse centre & faubourgs" and nc.zone_for(d, "31240")[0].startswith("Fondeyre")
    assert nc.zone_for(d, "Saint-Jean près de Toulouse")[0].startswith("Fondeyre") and nc.zone_for(d, "Sète") == (None, [])


async def test_city_unknown_asks_for_it_and_sets_no_default_days():
    erp = FakeErp()
    out = await register(erp, company_name="Le Comptoir", request="crème 5 L", kind="restaurant")
    assert out["cityUnknown"] and "sa ville" in out["next"] and erp.posts[0][1]["deliveryDays"] == []


async def test_a_repeated_request_is_not_noted_twice_and_the_card_is_returned():
    erp = FakeErp()
    out = await register(erp, company_name="Boulangerie du Canal", request="10 sacs de tradi pour jeudi (prix demandé)", phone="07 99 99 99 99")
    assert out["requestAlreadyNoted"] and erp.posts == [] and not out["created"]
    before = ["10 sacs de tradi pour jeudi · contact : X"]
    assert not nc.already_said("3 kg de levure", before) and not nc.already_said("beurre", before)
    assert nc.already_said("10 sacs de tradi pour jeudi. Adresse : 3 rue des Lilas, Colomiers", before, "3 rue des Lilas Colomiers")


async def test_a_prospect_calling_back_stays_a_new_client_with_its_card():
    from app.agent import call_context as cc_mod

    cc_mod.clear_cache()
    cc = await cc_mod.caller_context(FakeErp(), phone="07 99 99 99 99", contact_name="Camille")
    text = cc_mod.render_for_prompt(cc)
    assert cc.is_new and cc.client_id == "cli_0070" and "NOUVEAU CLIENT" in text
    assert "12 quai du Canal, Toulouse" in text and "Déjà noté : 10 sacs de tradi pour jeudi" in text
    cc_mod.clear_cache()


def test_no_order_tool_for_a_new_client_names_real_tools():
    from app.agent.call_context import NO_ORDER_FOR_NEW
    from app.tools import order_edit, order_place, order_review, orders  # noqa: F401  (registers them)

    assert NO_ORDER_FOR_NEW <= set(TOOLS) and "register_new_client" not in NO_ORDER_FOR_NEW


def test_a_question_is_not_asked_twice_in_a_row():
    from app.services.voice_reply import without_repeated_question

    before = "Deux kilos de beurre, c'est noté. Pour le beurre, vous le voulez doux ou plutôt de tourage ?"
    again = "Non, rien n'est confirmé pour demain, l'équipe vous rappelle. Pour le beurre, c'est du tourage ou du doux ?"
    assert without_repeated_question(again, before) == "Non, rien n'est confirmé pour demain, l'équipe vous rappelle."
    other = "C'est noté. Vous êtes dans quelle ville ?"
    assert without_repeated_question(other, before) == other and without_repeated_question("Pour le beurre ?", before) == "Pour le beurre ?"


def test_a_new_quantity_is_news_and_a_reworded_question_is_still_a_repeat():
    from app.services.voice_reply import without_repeated_question

    before = ["Beurre de tourage, 10 kg, type à préciser (AOP ou standard) · contact : Lucien"]
    assert not nc.already_said("Beurre de tourage, 15 kg (modifié, au lieu de 10 kg), type à préciser (AOP ou standard).", before)
    q1 = "C'est noté. Pour le beurre, c'est du beurre de tourage ou du beurre doux, et en quelle quantité par semaine ?"
    q2 = "Non, pas le samedi. Pour le beurre, vous le voulez en tourage ou en beurre doux ?"
    assert without_repeated_question(q2, q1) == "Non, pas le samedi."
    assert without_repeated_question("C'est noté. Vous le préférez AOP ou standard ?", "Vous le voulez AOP Charentes-Poitou ou standard ?") == "C'est noté."
    assert without_repeated_question("Et dans quelle ville ?", q1) == "Et dans quelle ville ?"


async def test_the_client_list_is_read_fresh_on_every_call():
    erp = FakeErp()
    await nc._directory(erp)
    CLIENTS.append({"id": "cli_0200", "name": "Tout Neuf", "status": "prospect", "contacts": [{"name": "Z", "phone": "06 01 01 01 01"}]})
    try:
        out = await register(erp, company_name="Autre", request="farine", phone="06 01 01 01 01")
        assert out["clientId"] == "cli_0200" and not out["created"]  # seen at once, not after a cache expiry
    finally:
        CLIENTS.pop()
