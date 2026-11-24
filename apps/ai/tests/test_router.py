"""TEAM_ROUTER: simple replies to the fast model; « D'accord, je regarde ça » only when there is something to look up."""

import pytest

from app.agent.router import is_simple_turn, pick_llm
from app.services import fillers

SIMPLE = [
    "That's right, please confirm.", "Confirmed.", "Yes.", "Yeah, go ahead.", "Perfect, thanks!", "Thank you, goodbye.", "Okay, sounds good.",
    "Yes, that's right.", "No thanks, that's all.", "Okay.", "Okay, go ahead.", "Please confirm.",
]
NOT_SIMPLE = [
    "Yes, but make it twelve.", "How much is a sack?", "I need ten sacks of traditional flour for Thursday.",
    "Actually, remove the rye.", "Is Thursday okay?", "Yes, and add two blocks of yeast.",
    "No, Friday instead.", "This morning's delivery was missing two sacks.",
]


@pytest.mark.parametrize("said", SIMPLE)
def test_simple_replies(said):
    assert is_simple_turn(said)


@pytest.mark.parametrize("said", NOT_SIMPLE)
def test_replies_that_need_the_main_model(said):
    assert not is_simple_turn(said)


def test_pick_llm_follows_the_switch(monkeypatch):
    main, fast = object(), object()
    monkeypatch.delenv("TEAM_ROUTER", raising=False)
    assert pick_llm("That's right, please confirm.", main, lambda: fast) == (main, "main")
    monkeypatch.setenv("TEAM_ROUTER", "1")
    assert pick_llm("That's right, please confirm.", main, lambda: fast) == (fast, "fast")
    assert pick_llm("Yes, but make it twelve.", main, lambda: fast) == (main, "main")

    def broken():
        raise RuntimeError("no fast model")

    assert pick_llm("Thanks.", main, broken) == (main, "main")


@pytest.mark.parametrize("said", SIMPLE)
def test_no_acknowledgement_for_a_confirmation(said):
    assert not fillers.needs_lookup(said)


@pytest.mark.parametrize(
    "said",
    ["Yes, but make it twelve.", "How much is a sack?", "I need ten sacks of traditional flour for Thursday.",
     "Actually, remove the rye.", "No, Friday instead."],
)
def test_acknowledgement_when_there_is_something_to_look_up(said):
    assert fillers.needs_lookup(said)


def test_erp_codes_are_never_said():
    from app.services.voice_reply import spoken_reply

    assert spoken_reply("Confirmed, Nadine. Your order CMD-2026-007543 is confirmed for Thursday.") == (
        "Confirmed, Nadine. Your order is confirmed for Thursday."
    )
    assert spoken_reply("Order number CMD-2026-000123, for delivery tomorrow.") == "Order, for delivery tomorrow."
    assert spoken_reply("I added prd_0001 to the order.") == "I added to the order."
    assert spoken_reply("Eighteen euros ninety per 25-kilo sack.") == "Eighteen euros ninety per 25-kilo sack."
