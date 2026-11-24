"""Youssef · fixes from the 150 test calls (24/11): real « oui », spoken reasoning, J-3, latest orders."""

import asyncio

import pytest

from app.agent.call_context import CallContext, describe_order, order_lead_days, render_for_prompt
from app.agent.listening import LISTENING_RULES, explicit_yes
from app.services.voice_reply import spoken_reply


@pytest.mark.parametrize("answer", ["Pour jeudi.", "Vendredi.", "Lundi", "Combien ça fait ?", "Et du sel aussi.", "Mercredi."])
def test_a_day_or_a_question_is_not_a_yes(answer):
    assert not explicit_yes(answer)


@pytest.mark.parametrize("answer", ["Oui.", "Ouais", "Ok c'est bon", "C'est ça, merci.", "D'accord, validez.", "Parfait, je valide.",
                                    "Ça marche", "Oui oui, confirmez.", "Allez-y", "Très bien, oui."])
def test_real_yes(answer):
    assert explicit_yes(answer)


def test_confirm_order_refuses_a_bare_day_without_asking_jev_or_the_erp(monkeypatch):
    from app.tools import order_jev
    from app.tools.registry import ToolContext

    class Erp:
        posted = []

        async def get(self, path, params=None):
            return {"id": "ord_1", "warnings": []}

        async def post(self, path, body=None):
            self.posted.append(path)
            return {}

    erp = Erp()
    r = asyncio.run(order_jev.confirm_order.fn(ToolContext(erp=erp, actor="voice_agent"), "ord_1", "Vendredi.", "Je vous la valide ?"))
    assert r["confirmed"] is False and "redemande" in r["next"] and erp.posted == []
    r = asyncio.run(order_jev.confirm_order.fn(ToolContext(erp=erp, actor="voice_agent"), "ord_1", None, None))
    assert r["confirmed"] is False and erp.posted == []


def test_the_agent_explaining_its_rules_is_not_spoken():
    raw = ("La fiche du client dit qu'il accepte les substitutions équivalentes si on le prévient, donc je propose le remplaçant.\n\n"
           "Le tourage AOP est en rupture, mais j'ai le tourage 82 %.")  # fmt: skip
    assert spoken_reply(raw) == "Le tourage AOP est en rupture, mais j'ai le tourage 82 %."
    assert spoken_reply("Selon sa fiche, il veut du 64. Je vous mets la couverture noire 64 ?") == "Je vous mets la couverture noire 64 ?"
    assert spoken_reply("Bonjour Nadine, je vous écoute.") == "Bonjour Nadine, je vous écoute."  # normal replies untouched


def test_ordering_lead_time_and_latest_orders_are_in_the_sheet():
    assert order_lead_days("Bon de commande à J-3 avant midi, ovoproduits liquides uniquement") == 3
    assert order_lead_days("Livraison avant 11h") is None
    line = describe_order({"deliveryDate": "2026-11-26", "status": "confirmed", "totalHt": 151.0, "lineCount": 2},
                          {"lines": [{"productName": "Farine tradi", "qty": 10, "unit": "piece"}]})  # fmt: skip
    assert line.startswith("jeudi 26/11 · confirmée · 151 €") and "10 piece Farine tradi" in line
    cc = CallContext(client_id="cli_0005", name="Cuisine centrale", delivery_days=["wed"],
                     preferences="Bon de commande à J-3 avant midi.", recent_orders=[line])  # fmt: skip
    sheet = render_for_prompt(cc)
    assert "Délai de commande : J-3" in sheet and "Dernières commandes" in sheet and "Farine tradi" in sheet


def test_conversation_rules_ask_closed_questions_and_summarise_long_lists():
    assert "jamais « A ou B ? »" in LISTENING_RULES and "Plus de 4 produits" in LISTENING_RULES
