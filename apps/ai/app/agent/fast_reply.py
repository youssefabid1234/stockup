"""
OWNER: Amine Khalil (vitesse) · switch TEAM_FAST_REPLY

An order step costs TWO model calls: one to call place_order, a second one only to write the read-back that
place_order already returns, ready to say (rules_order.review). Same for « c'est validé » after confirm_order. When the
tool's result is clean (written, nothing to ask, no alert, no duplicate, no question pending), the reply is composed
here from the tool's own words and the second model call is skipped (~1 s per order step, measured 24/11).
Anything unusual (alert, unusual quantity, franco with a question, duplicates, « next »…) goes back to the model as before.
"""

from __future__ import annotations

import re

from app import team_flags

_NOT_CLEAN = ("alerts", "askFirst", "duplicateDrafts", "sameDayOrders", "blockedBy", "next", "short", "unclear")


def _lower_names(readback: str) -> str:
    """« 10 sacs de Farine de blé T55 » → « 10 sacs de farine de blé T55 » (a name in the middle of a sentence)."""
    return re.sub(r"\b(de |d')([A-ZÉÈ])(?=[a-zéèêàç])", lambda m: m.group(1) + m.group(2).lower(), readback)


def compose(mode: str, calls: list, results: list) -> str | None:
    """The reply to say without a second model call, or None (the model writes it, as before)."""
    if not team_flags.fast_reply() or mode != "voice" or len(calls) != 1 or len(results) != 1:
        return None
    r = results[0]
    res = r.result if r.ok and isinstance(r.result, dict) else None
    if not res:
        return None
    if r.name == "place_order":
        if not res.get("written") or res.get("canConfirm") is not True or any(res.get(k) for k in _NOT_CLEAN):
            return None
        readback = res.get("readback")
        if not readback:
            return None
        from app.agent.rules_order import fr_money

        said = _lower_names(readback).replace(" ; livraison ", ", livraison ")
        if res.get("franco"):
            return f"Je vous note {said}. Attention, {res['franco']}. Je vous la valide quand même ?"
        total = f", pour {fr_money(res['totalHt'])} hors taxes" if res.get("totalHt") else ""
        return f"Je vous note {said}{total}. Je vous la valide ?"
    if r.name == "confirm_order" and res.get("confirmed") is True:
        if res.get("alreadyConfirmed"):
            return "C'est bon, elle était déjà validée et vos changements y sont. Il vous faut autre chose ?"
        return "C'est validé, merci ! Il vous faut autre chose ?"
    return None
