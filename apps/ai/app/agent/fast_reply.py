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


_TU = re.compile(r"\b(?:tu|toi|ton|ta|tes|te)\b|\bt'", re.I)


def _says_tu(messages: list | None) -> bool:
    """The agent already says « tu » to this caller (Daycem's tone rules: « Salut Thierry »): keep it."""
    for m in reversed(messages or []):
        if getattr(m, "role", None) == "assistant" and (m.content or "").strip():
            return bool(_TU.search(m.content))
    return False


def _de(word: str) -> str:
    return "d'" if word[:1].lower() in "aeiouyéèêàh" else "de "


def _items(readback_items: str, call) -> str:
    """The products as the CALLER said them when the order is new and each line maps one to one (« 5 sacs de tradi »
    rather than « 5 sacs de farine de blé T55 tradition française ») ; else the catalogue names."""
    parts = [p.strip() for p in readback_items.split(", ") if p.strip()]
    args = getattr(call, "arguments", None) or {}
    lines = args.get("lines") or []
    if args.get("orderId") or args.get("order_id") or len(lines) != len(parts) or not all(li.get("said") for li in lines):
        return _lower_names(readback_items)
    out = []
    for part, line in zip(parts, lines, strict=True):
        quantity = part.split(" de ", 1)[0].split(" d'", 1)[0]  # « 5 sacs », « 30 kilos » : the converted quantity
        said = line["said"].strip()
        out.append(f"{quantity} {_de(said)}{said}")
    return ", ".join(out[:-1]) + (" et " if len(out) > 1 else "") + out[-1]


# team 12 (Amine K.): a familiar, varied counter voice (« Alors, c'est noté… Pour vous ça sera… hmm, un total de… »).
# The variant is chosen from the order itself (stable for the same order, different from one order to the next).
OPENERS = ["C'est noté :", "Alors, c'est noté :", "Bon, c'est noté :", "Nickel, je vous note :", "Ça marche, je vous mets :"]
OPENERS_TU = ["C'est noté :", "Alors, c'est noté :", "Bon, c'est noté :", "Nickel, je te note :", "Ça marche, je te mets :"]
TOTALS = ["Pour vous ça sera… hmm, un total de {m} hors taxes.", "Ça vous fait {m} hors taxes en tout.",
          "Et au total, ça fait {m} hors taxes."]
TOTALS_TU = ["Pour toi ça sera… hmm, un total de {m} hors taxes.", "Ça te fait {m} hors taxes en tout.",
             "Et au total, ça fait {m} hors taxes."]
ASKS = ["Je vous la valide ?", "On part là-dessus ?", "Je vous la passe comme ça ?"]
ASKS_TU = ["Je te la valide ?", "On part là-dessus ?", "Je te la passe comme ça ?"]
DONE = ["C'est validé, merci ! Il vous faut autre chose ?", "Et voilà, c'est validé ! Autre chose pour vous ?",
        "Ça roule, c'est validé ! Je peux faire autre chose pour vous ?", "Çaaa marche, c'est validé ! Il vous faut autre chose ?"]
DONE_TU = ["C'est validé, merci ! Il te faut autre chose ?", "Et voilà, c'est validé ! Autre chose pour toi ?",
           "Ça roule, c'est validé ! Je peux faire autre chose pour toi ?", "Çaaa marche, c'est validé ! Il te faut autre chose ?"]


def _pick(options: list[str], key: str) -> str:
    import zlib

    return options[zlib.crc32(key.encode("utf-8")) % len(options)]


def compose(mode: str, calls: list, results: list, messages: list | None = None) -> str | None:
    """The reply to say without a second model call, or None (the model writes it, as before)."""
    if not team_flags.fast_reply() or mode != "voice" or len(calls) != 1 or len(results) != 1:
        return None
    r = results[0]
    res = r.result if r.ok and isinstance(r.result, dict) else None
    if not res:
        return None
    tu = _says_tu(messages)
    if r.name == "place_order":
        if not res.get("written") or res.get("canConfirm") is not True or any(res.get(k) for k in _NOT_CLEAN):
            return None
        readback = res.get("readback")
        if not readback:
            return None
        from app.agent.rules_order import fr_money

        items, _, day = readback.partition(" ; livraison ")
        said = _items(items, calls[0])
        when = (f", et tu seras livré {day}" if tu else f", et vous serez livrés {day}") if day else ""
        opener = _pick(OPENERS_TU if tu else OPENERS, readback)
        total = res.get("totalHt")
        if res.get("franco") and total:
            ask = "Je te la valide quand même ?" if tu else "Je vous la valide quand même ?"
            return (f"{opener} {said}{when}. Ça fait {fr_money(total)} hors taxes, donc bon, il y aura 12 euros de frais "
                    f"de livraison : c'est offert à partir de 150 euros. {ask}")
        money = (" " + _pick(TOTALS_TU if tu else TOTALS, readback + "t").format(m=fr_money(total))) if total else ""
        return f"{opener} {said}{when}.{money} {_pick(ASKS_TU if tu else ASKS, readback + 'a')}"
    if r.name == "confirm_order" and res.get("confirmed") is True:
        other = "Il te faut autre chose ?" if tu else "Il vous faut autre chose ?"
        if res.get("alreadyConfirmed"):
            return f"C'est bon, elle était déjà validée et les changements y sont. {other}"
        return _pick(DONE_TU if tu else DONE, str(res.get("id") or res.get("number") or res))
    return None
