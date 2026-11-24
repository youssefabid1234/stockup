"""Youssef · caller ID before the call: who calls is known before the first word (ERP client by id or phone, or new)."""

import pytest

from app.agent import call_context as cc_mod
from app.agent.call_context import caller_context, render_for_prompt
from app.schemas import CallerMessage, CallerReadyMessage

SARRAILH = {
    "id": "cli_0001", "name": "Maison Sarrailh", "status": "active", "deliveryDays": ["tue", "thu", "sat"],
    "contacts": [{"name": "Nadine Sarrailh", "role": "Boutique et commandes", "phone": "05 61 21 33 47"}],
    "preferences": "Jamais de substitution sur le beurre.", "usual": [], "notes": [],
}  # fmt: skip


class FakeErp:
    def __init__(self):
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append(path)
        if path == "/api/clients":
            return [SARRAILH, {"id": "cli_0002", "name": "Autre", "contacts": [{"name": "X", "phone": "06 00 00 00 00"}]}]
        if path.startswith("/api/clients/"):
            return SARRAILH
        if path == "/api/context/for":
            return {"entries": []}
        raise AssertionError(path)


@pytest.fixture(autouse=True)
def fresh_cache():
    cc_mod.clear_cache()
    yield
    cc_mod.clear_cache()


async def test_known_client_by_id():
    cc = await caller_context(FakeErp(), client_id="cli_0001", contact_name="Nadine Sarrailh")
    text = render_for_prompt(cc)
    assert cc.name == "Maison Sarrailh" and "Au téléphone : Nadine Sarrailh" in text and "ne le recherche pas" in text


async def test_known_client_by_phone_any_format():
    cc = await caller_context(FakeErp(), phone="+33 5 61 21 33 47")
    assert cc.client_id == "cli_0001" and cc.caller_contact == "Nadine Sarrailh"


async def test_unknown_phone_is_a_new_client():
    cc = await caller_context(FakeErp(), phone="07 99 99 99 99", contact_name="Camille", company_name="Boulangerie du Canal")
    assert cc.is_new and cc.client_id == "" and cc.name == "Boulangerie du Canal"
    text = render_for_prompt(cc)
    assert "NOUVEAU CLIENT" in text and "Ne crée et ne confirme AUCUNE commande" in text and "Camille" in text


async def test_ticked_new_client_with_a_known_phone_is_that_client():
    cc = await caller_context(FakeErp(), is_new=True, company_name="Sarrailh", phone="05 61 21 33 47")
    assert not cc.is_new and cc.client_id == "cli_0001"  # the box was ticked by mistake: no duplicate prospect


async def test_ticked_new_client_with_an_unknown_phone_stays_new_and_keeps_the_form():
    cc = await caller_context(FakeErp(), is_new=True, contact_name="Karim", phone="06 55 55 55 55")
    text = render_for_prompt(cc)
    assert cc.is_new and cc.company_name is None and "Établissement : pas encore connu" in text
    cc = await caller_context(FakeErp(), is_new=True, company_name="Chez Paul", phone="06 55 55 55 55")
    assert "Établissement (donné avant l'appel, ne le redemande pas) : Chez Paul" in render_for_prompt(cc)


async def test_nothing_given_no_sheet():
    assert await caller_context(FakeErp()) is None


def test_wire_messages():
    m = CallerMessage.model_validate({"type": "caller", "clientId": "cli_0001", "contactName": "Nadine"})
    assert m.client_id == "cli_0001" and not m.is_new
    out = CallerReadyMessage(name="Maison Sarrailh", client_id="cli_0001", used_by_agent=True).to_json()
    assert '"type":"caller_ready"' in out and '"usedByAgent":true' in out
