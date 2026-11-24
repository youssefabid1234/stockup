"""Keep model notes out of the final spoken reply."""

import re

_INTERNAL_BLOCK = re.compile(r"<(think|thinking|analysis|reasoning)\b[^>]*>.*?(?:</\1\s*>|$)", re.I | re.S)
_INTERNAL_LEAD = re.compile(
    r"^\s*(?:[-*#>\[]\s*)*(?:"
    r"(?:analyse|raisonnement|note interne|plan)\s*\]?\*{0,2}\s*:|"
    r"(?:d'abord,?\s+)?(?:je dois|il faut que je|je vais devoir)\s+"
    r"(?:d'abord\s+)?(?:vérifier|chercher|consulter|identifier|utiliser|appeler|répondre|déterminer|comprendre)\b|"
    r"ma réponse (?:doit|sera|va)\b|"
    # team 12 (Youssef): the model explaining its own rules (heard in the 150 test calls, 24/11)
    r"(?:la|sa) fiche(?: du client| client)?\s+(?:dit|indique|précise|mentionne|montre)\b|"
    r"(?:d['’]après|selon) (?:la|sa) fiche\b|"
    r"(?:la|ma) (?:règle|consigne)\s+(?:dit|est|veut|impose)\b|"
    r"(?:le client|l['’]appelant|l['’]utilisateur)\s+(?:demande|souhaite|veut)\b"
    r")",
    re.I,
)
# team 12 (Youssef, natural voice): a leading acknowledgement word, and its variants for vary_opening
_OPENER = re.compile(r"^\s*(parfait|très bien|tres bien|d['’]accord|entendu|ok|okay|alors|bon|super|ça marche|c['’]est noté|bien sûr)\s*[,.!…]+\s*", re.I)


def vary_opening(reply: str, previous: str | None) -> str:
    """Drop the leading « Parfait, » (or « Très bien, », « D'accord, »…) when the previous reply of the call began with
    the same word: the guides' first sign of a robotic agent. The rest of the sentence is kept, capitalised."""
    m, prev = _OPENER.match(reply or ""), _OPENER.match(previous or "")
    if not m or not prev or m.group(1).lower().replace("’", "'") != prev.group(1).lower().replace("’", "'"):
        return reply
    rest = reply[m.end():]
    return rest[:1].upper() + rest[1:] if rest else reply


_REPLY_LABEL = re.compile(r"^\s*\*{0,2}réponse(?: au client| finale)?\s*:\*{0,2}\s*", re.I)
_GREETING = re.compile(r"^\s*(?:bonjour|bonsoir)\b", re.I)
_SENTENCE_BREAK = re.compile(r"(?<=[.!?…])\s+|\n+")


# ERP codes are never said on the phone (« votre commande CMD-2026-007543 est confirmée » was heard with the fast model)
_CODE = r"(?:CMD|ACH|FAC|AV)-\d{4}-\d+|\b(?:cli|prd|ord|sup|lin|po|pol|ctx|rte|prl)_\d+\b"
_NUMBERED = re.compile(rf"\s*(?:,\s*)?(?:(?:la |le |votre |n°\s*|numéro\s*|référence\s*)*)(?:{_CODE})(?=[\s.,;:!?)]|$)", re.I)


def without_codes(text: str) -> str:
    """« Votre commande CMD-2026-007543 est confirmée » → « Votre commande est confirmée »."""
    cleaned, found = _NUMBERED.subn("", text)
    if not found:
        return text  # untouched: French spacing before « ? » / « : » stays as the model wrote it
    return re.sub(r"\s{2,}", " ", re.sub(r"\s+([.,;])", r"\1", cleaned)).strip()


def spoken_reply(text: str) -> str:
    """Strip explicit internal blocks, obvious leading notes and ERP codes from a final model message."""
    text = without_codes(_INTERNAL_BLOCK.sub("", text)).strip()
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
