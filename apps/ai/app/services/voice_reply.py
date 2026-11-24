"""Keep model notes out of the final spoken reply."""

import re

_INTERNAL_BLOCK = re.compile(r"<(think|thinking|analysis|reasoning)\b[^>]*>.*?(?:</\1\s*>|$)", re.I | re.S)
_INTERNAL_LEAD = re.compile(
    r"^\s*(?:[-*#>\[]\s*)*(?:"
    r"(?:analyse|raisonnement|note interne|plan)\s*\]?\*{0,2}\s*:|"
    r"(?:d'abord,?\s+)?(?:je dois|il faut que je|je vais devoir)\s+"
    r"(?:d'abord\s+)?(?:vérifier|chercher|consulter|identifier|utiliser|appeler|répondre|déterminer|comprendre)\b|"
    r"ma réponse (?:doit|sera|va)\b|"
    r"(?:le client|l['’]appelant|l['’]utilisateur)\s+(?:demande|souhaite|veut)\b"
    r")",
    re.I,
)
_REPLY_LABEL = re.compile(r"^\s*\*{0,2}réponse(?: au client| finale)?\s*:\*{0,2}\s*", re.I)
_GREETING = re.compile(r"^\s*(?:bonjour|bonsoir)\b", re.I)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?…])\s+|\n+")


def spoken_reply(text: str) -> str:
    """Strip explicit internal blocks and obvious leading notes from a final model message."""
    text = _INTERNAL_BLOCK.sub("", text).strip()
    segments = _SENTENCE_BREAK.split(text)
    if segments and _INTERNAL_LEAD.match(segments[0]):
        # When an obvious note precedes the greeting, discard the entire preamble.
        for i, part in enumerate(segments[1:], start=1):
            if _GREETING.match(part) or _REPLY_LABEL.match(part):
                return _REPLY_LABEL.sub("", " ".join(segments[i:])).strip()
        while segments and _INTERNAL_LEAD.match(segments[0]):
            segments.pop(0)
        text = " ".join(segments).strip()
    return _REPLY_LABEL.sub("", text)


def without_repeated_greeting(reply: str, contact: str | None) -> str:
    """Drop just the greeting when the caller has already heard our prepared clip."""
    address = r"(?:madame|monsieur)"
    if contact:
        name = " ".join(contact.split())
        if name:
            names = "|".join(re.escape(part) for part in dict.fromkeys((name, *name.split())))
            address = rf"(?:{address})(?:\s+(?:{names}))?|{names}"
    prefix = rf"^(?:bonjour|bonsoir)(?:[ ,]+(?:{address}))?(?:[.!?,…]+\s*|\s*$)"
    remaining = re.sub(prefix, "", reply, count=1, flags=re.I)
    if remaining != reply and remaining:
        return remaining[0].upper() + remaining[1:]
    return remaining
