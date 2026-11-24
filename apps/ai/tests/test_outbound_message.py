"""Youssef · Lucie's voice message after an unanswered outbound call: her wording if it invents nothing, else a fixed one."""

from app.clients.base import LLMText
from app.services.outbound_message import acceptable, compose, facts_of, template

ATTEMPT = {
    "clientName": "La Mie de Saint-Michel",
    "offer": {"productId": "prd_0026", "productName": "Beurre de tourage 82 % (plaque 2 kg)", "kind": "promo", "unit": "kg",
              "unitPrice": 8.46, "validUntil": "2026-11-30", "purchaseCount": 8},
}  # fmt: skip


class FakeLLM:
    def __init__(self, text):
        self.text = text

    async def stream(self, req):
        yield LLMText(delta=self.text)


def test_facts_are_said_like_in_the_calls():
    f = facts_of(ATTEMPT, "Kevin Bonnafous")
    assert f["prénom"] == "Kevin" and f["prix hors taxes"] == "8 euros 46 le kilo" and f["jusqu'au"] == "30 novembre"
    assert f["produit"] == "beurre de tourage 82 %"
    assert acceptable(template(f), f)


async def test_the_models_wording_is_kept_when_it_invents_nothing():
    f = facts_of(ATTEMPT, "Kevin Bonnafous")
    good = ("Bonjour Kevin, c'est Lucie du Fournil Occitan. Le beurre de tourage 82 % que vous prenez souvent est à "
            "8 euros 46 le kilo jusqu'au 30 novembre. Rappelez-moi quand vous voulez. Belle journée !")
    assert await compose(f, lambda: FakeLLM(good)) == (good, "modèle")


async def test_an_invented_number_falls_back_to_the_fixed_message():
    f = facts_of(ATTEMPT, "Kevin Bonnafous")
    bad = "Bonjour Kevin, c'est Lucie du Fournil Occitan. Moins 15 % sur le beurre jusqu'au 30 novembre ! Belle journée !"
    text, source = await compose(f, lambda: FakeLLM(bad))
    assert source == "gabarit" and "15" not in text and text.startswith("Bonjour Kevin")


async def test_no_model_still_leaves_a_message():
    def broken():
        raise RuntimeError("no fast model")

    text, source = await compose(facts_of(ATTEMPT, None), broken)
    assert source == "gabarit" and text.startswith("Bonjour, c'est Lucie")
