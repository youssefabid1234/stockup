"""
OWNER: Amine Khalil · switch TEAM_ROUTER · « le bon modèle pour chaque réplique »

Most replies of a phone order are simple: « c'est bon, validez », « oui », « parfait », « merci, au revoir ». They need
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
    r"oui|ouais|ouai|ok|okay|d'accord|daccord|parfait|très bien|tres bien|super|impeccable|nickel|génial|"
    r"c'est bon|c'est parfait|c'est tout bon|c'est ok|ça marche|ca marche|ça me va|ca me va|ça roule|"
    r"validez|validez-la|validez la|validé|valide|validée|je valide|on valide|confirmez|confirmez-la|confirmé|je confirme|"
    r"allez-y|allez y|vas-y|vas y|go|banco|top|"
    r"merci|merci beaucoup|merci bien|au revoir|bonne journée|bonne soirée|à bientôt|a bientot|"
    r"c'est tout|c'est tout pour moi|ce sera tout|rien d'autre|non merci|non c'est tout|non|"
    r"voilà|voila|bon|bah|ben|alors|écoutez|euh|hum"
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
            return fast_llm_factory(), "rapide"
        except Exception:  # fast model not configured: the main one
            return main_llm, "principal"
    return main_llm, "principal"
