"""Team 12 · Daycem (T5) · price negotiation: no discount, no internal threshold said, the request recorded as
price_negotiation, and the client's own sales rep read from the ERP card (never guessed)."""

import pytest

from app.agent import call_context as cc_mod
from app.agent import rules_sales
from app.agent.call_context import CallContext, render_for_prompt


def _bullet(rules: str, start: str) -> str:
    return next(line for line in rules.splitlines() if line.startswith(start))


def test_negotiation_rule_fr():
    rule = _bullet(rules_sales.SALES_RULES, "- Demande de remise")
    assert "aucune remise" in rule and "chaque relance" in rule
    assert "ne cite jamais de seuil ni de pourcentage interne" in rule
    assert "Si le client accepte, enregistre sa demande avec log_client_event, type price_negotiation" in rule
    assert "celui que donne sa fiche" in rule and "2 phrases" in rule
    assert "par son prénom et son nom" in rule and "« notée pour »" in rule and "jamais « transmise »" in rule
    assert "propose de la transmettre" not in rule


def test_negotiation_rule_en():
    rule = _bullet(rules_sales.SALES_RULES_EN, "- Discount request")
    assert "neither grant nor promise any discount" in rule and "every follow-up" in rule
    assert "never quote an internal threshold or percentage" in rule
    assert "If the client accepts, record their request with log_client_event, type price_negotiation" in rule
    assert "the one their card gives" in rule and "2 sentences" in rule
    assert "by first and last name" in rule and "« noted for »" in rule and "never « passed on »" in rule
    assert "offer to pass it on" not in rule


def test_negotiation_rule_names_no_one():
    for rules in (rules_sales.SALES_RULES, rules_sales.SALES_RULES_EN):
        rule = _bullet(rules, "- Demande de remise" if rules is rules_sales.SALES_RULES else "- Discount request").lower()
        for specific in ["bernard", "castagné", "marion", "escudié", "julien", "fabre", "muret", "escaich", "5 %"]:
            assert specific not in rule, specific


def test_sheet_shows_the_sales_rep_in_one_line():
    without = render_for_prompt(CallContext(client_id="c1", name="Boulangerie X"))
    with_rep = render_for_prompt(CallContext(client_id="c1", name="Boulangerie X", sales_rep="Anne Martin"))
    assert "- Commercial(e) : Anne Martin" in with_rep
    assert len(with_rep.splitlines()) == len(without.splitlines()) + 1
    assert "Commercial" not in without and "None" not in without


class _Erp:
    def __init__(self, client: dict):
        self.client = client

    async def get(self, path, params=None):
        if path.startswith("/api/clients/"):
            return self.client
        return {"entries": []} if path.startswith("/api/context") else []


@pytest.mark.parametrize(("card", "expected"), [({"salesRep": "Anne Martin"}, "Anne Martin"), ({}, None),
                                                ({"salesRep": ""}, None)])  # fmt: skip
async def test_sales_rep_is_read_from_the_card(card, expected):
    sheet = await cc_mod.load_call_context(_Erp({"id": "c1", "name": "Boulangerie X", **card}), "c1")
    assert sheet.sales_rep == expected
    assert ("Commercial(e)" in render_for_prompt(sheet)) is (expected is not None)
