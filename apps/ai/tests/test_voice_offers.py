"""Regression tests for offers that share the microphone with an order."""

from unittest.mock import AsyncMock

import pytest

from app.agent.call_context import CallContext
from app.schemas import DoneEvent, ChatMessage, ToolResultEvent
from app.services import voice_offers, voice_session

OFFER = {
    "id": "promo:prd_26:rule", "productId": "prd_26", "productName": "Beurre de tourage 82 % (plaque 2 kg)",
    "kind": "promo", "unit": "kg", "unitPrice": 8.46, "caliber": "carton 5 plaques de 2 kg",
    "ruleId": "rule", "validUntil": "2026-11-30", "quantity": 10, "purchaseCount": 6,
}
ORDER = {"id": "ord_001", "lines": [{"id": "lin_001", "productId": "prd_26"}], "status": "draft"}
REVIEW = {"orderId": "ord_001", "readback": "Deux plaques de beurre", "canConfirm": True}


@pytest.mark.parametrize(("said", "qty"), [
    ("Ajoutez-en deux cartons", 20), ("Mettez-moi 3 plaques", 6), ("Ajoutez-en deux", 20),
    ("Ajoutez deux plaques de beurre de tourage 82 %", 4),
    ("Ajoutez deux cartons de farine", None), ("Oui", None), ("Ajoutez une caisse", None),
    ("Ajoutez deux cartons et annulez la livraison", None), ("Oui mais mettez-moi trois cartons", 30),
])
def test_quantity_is_tied_to_the_offered_product(said, qty):
    assert voice_offers.amount_requested(voice_offers.normalized(said), OFFER) == qty


@pytest.fixture
def offers():
    state = voice_offers.CallOffers("cli_01", "voice-test")
    state.erp = AsyncMock()
    state.erp.get.return_value = [OFFER]
    state.erp.post.return_value = ORDER
    state._review = AsyncMock(return_value=REVIEW)
    return state


async def test_yes_to_a_price_does_not_place_an_order(offers):
    offers.pending = OFFER
    reply = await offers.respond("Oui")
    assert "Quelle quantité" in reply.text
    offers.erp.post.assert_not_called()
    reply = await offers.respond("Deux cartons")
    assert reply.awaiting_confirmation
    assert "20 kilos" in reply.text
    assert "Je vous valide" in reply.text
    assert offers.erp.post.await_args.args[1]["quantity"] == 20
    assert offers.pending is None


async def test_outbound_permission_then_refusal(offers):
    offers.outbound = {"offer": OFFER}
    offers.permission = True
    reply = await offers.respond("Non merci")
    assert "bonne journée" in reply.text
    assert offers.pending is None
    assert offers.erp.post.await_args.args[0].endswith("/decline")


async def test_offer_replaced_on_the_safe_confirmation_question_only(offers):
    offers.draft = "ord_001"
    reply, selected = await offers.propose("Pour jeudi", "Pour jeudi. Je vous la valide ?", REVIEW)
    assert selected == OFFER
    assert reply.count("?") == 1 and "promo" in reply
    for heard, answer, review in (
        ("Merci c’est tout", "Je vous la valide ?", REVIEW),
        ("Pour jeudi", "Quelle farine ?", REVIEW),
        ("Pour jeudi", "Je vous la valide ?", {**REVIEW, "askFirst": ["200 sacs"]}),
        ("Pour jeudi", "Je vous la valide ?", {**REVIEW, "sameDayOrders": ["ord_002"]}),
    ):
        assert await offers.propose(heard, answer, review) == (answer, None)


async def test_confirm_requires_the_separate_clear_reply(offers, monkeypatch):
    offers.pending = OFFER
    offers.draft = "ord_001"
    tool = AsyncMock()
    tool.run.return_value = {**ORDER, "status": "confirmed"}
    monkeypatch.setitem(voice_offers.TOOLS, "confirm_order", tool)
    added = await offers.respond("Ajoutez-en deux plaques")
    tool.run.assert_not_called()
    offers.readback = added.text
    assert await offers.respond("Oui, mais jeudi") is None
    tool.run.assert_not_called()
    offers.readback = added.text
    reply = await offers.respond("Oui, je confirme")
    assert reply.order["status"] == "confirmed"
    assert tool.run.await_args.args[0]["clientAnswer"] == "Oui, je confirme"


async def test_accepted_offer_modifies_the_same_draft_in_the_voice_session(offers, monkeypatch):
    monkeypatch.setenv("TEAM_RECOMMENDATIONS", "1")
    monkeypatch.setenv("TEAM_FILLERS", "0")
    monkeypatch.setenv("TEAM_ROUTER", "0")
    monkeypatch.setenv("TEAM_ORCHESTRATOR", "0")
    connection = voice_session.VoiceConnection(None)
    connection.send, connection.send_bytes = AsyncMock(), AsyncMock()
    conversation = voice_session.Conversation("voice-test", offers=offers, call_context=CallContext("cli_01", "Boulanger"))
    async def model(messages, **_):
        yield ToolResultEvent(call_id="create", name="create_draft_order", ok=True, result=ORDER, ms=1)
        yield ToolResultEvent(call_id="review", name="review_order", ok=True, result=REVIEW, ms=1)
        yield DoneEvent(message=ChatMessage(role="assistant", content="C’est noté. Je vous la valide ?"), ms=2)
    monkeypatch.setattr(voice_session, "run_agent", model)
    await connection.run_turn(conversation, text="Je voudrais dix sacs de farine.")
    assert offers.pending == OFFER, [getattr(call.args[0], "message", "") for call in connection.send.await_args_list]
    assert "promo" in conversation.history[-1].content
    await connection.run_turn(conversation, text="Ajoutez-en deux cartons.")
    body = offers.erp.post.await_args.args[1]
    assert body["orderId"] == "ord_001" and body["quantity"] == 20
    assert "récapitule" in conversation.history[-1].content
    assert offers.readback == conversation.history[-1].content


async def test_offer_is_also_available_on_explicit_request_without_a_draft(offers):
    reply = await offers.respond("Est-ce que vous avez des promotions en ce moment ?")
    assert reply.offered == OFFER
    assert "Quelle quantité" in reply.text
    assert offers.quoted
    offers.erp.post.assert_not_called()
