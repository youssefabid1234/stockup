"""
OWNER: Amine Khalil · switch TEAM_ROUTER · "the right model for each replica"

Most folds of a phone order are simple: "it's good, validate", "yes", "perfect", "thank you, goodbye".
one tool call at most (confirm_order, already guarded by Jev) and a short sentence: the fast model (Haiku,
TEAM_FAST_MODEL) does that 2-3× faster than Sonnet (measured with our settings: first word 0.45-0.57 s vs 1.19-1.33 s).
Everything else — a product, a quantity, a price, a change of mind, a complaint — stays on the main model (Sonnet),
which knows the trade better. Deterministic: a short closed list of confirmation / politeness phrases, nothing else.
"""

from __future__ import annotations

import re

from app import team_flags

# The whole utterance must be made of these (with punctuation): « Oui c'est bon, validez. » → simple ;
# « Oui mais mettez-en douze » / « c'est bon pour le seigle ? » → not simple (Sonnet).
_SIMPLE_PHRASES = (
    r"yes|yeah|yep|okay|ok|all right|alright|fine|perfect|great|sounds good|that's (?:right|fine|good|all)|"
    r"that is (?:right|fine|good|all)|please|you can|confirmed|confirm(?: (?:it|the order))?|go ahead|do it|"
    r"thank you(?: very much)?|thanks|goodbye|bye|have a (?:good|nice) day|no thanks|no|nothing else|well|um"
)


SIMPLE_TURN = re.compile(rf"^(?:[\s.,!?;:…\-]*(?:{_SIMPLE_PHRASES}))+[\s.,!?;:…\-]*$", re.I)


def is_simple_turn(heard: str) -> bool:
    """« C'est bon, validez. », « Oui. », « Merci, au revoir. » → True. Anything with a product, a number, a « mais »,
    a question about the order → False."""
    words = heard.replace("’", "'").strip()
    return bool(words) and bool(SIMPLE_TURN.fullmatch(words))


def pick_llm(heard: str, main_llm, fast_llm_factory):
    """(llm, label): the fast model for a simple reply when TEAM_ROUTER is on, else the main model."""
    if team_flags.router() and is_simple_turn(heard):
        try:
            return fast_llm_factory(), "fast"
        except Exception:  # fast model not configured: the main one
            return main_llm, "main"
    return main_llm, "main"
