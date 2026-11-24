"""Keep model notes out of the final spoken reply."""

import re

_INTERNAL_BLOCK = re.compile(r"<(think|thinking|analysis|reasoning)\b[^>]*>.*?(?:</\1\s*>|$)", re.I | re.S)
_INTERNAL_LEAD = re.compile(
    r"^\s*(?:[-*#>\[]\s*)*(?:(?:analysis|reasoning|internal note|plan)\s*\]?\*{0,2}\s*:|"
    r"(?:first,?\s+)?I (?:must|need to|have to|should) (?:first )?"
    r"(?:check|look|search|consult|identify|use|call|respond|determine|understand)\b|"
    r"my (?:response|answer) (?:must|will|should)\b|the (?:customer|caller|user) (?:asks|wants|needs|requested)\b)", re.I,
)
_REPLY_LABEL = re.compile(r"^\s*\*{0,2}(?:final (?:answer|response)|reply to (?:the )?(?:customer|caller)|answer|response)\s*:\*{0,2}\s*", re.I)
_GREETING = re.compile(r"^\s*(?:hello|hi|good (?:morning|afternoon|evening))\b", re.I)


_SENTENCE_BREAK = re.compile(r"(?<=[.!?…])\s+|\n+")


# ERP codes are never said on the phone ("your order CMD-2026-007543 is confirmed » was heart with the fast model)
_CODE = r"(?:CMD|ACH|FAC|AV)-\d{4}-\d+|\b(?:cli|prd|ord|sup|lin|po|pol|ctx|rte|prl)_\d+\b"
_NUMBERED = re.compile(rf"\s*(?:,\s*)?(?:(?:number |reference |no\. |n°\s*|numéro\s*|référence\s*)*)(?:{_CODE})(?=[\s.,;:!?)]|$)", re.I)


def without_codes(text: str) -> str:
    """« Your order CMD-2026-007543 is confirmed" → "Your order is confirmed"."""
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
    address = r"(?:ma['’]am|madam|sir)"
    if contact:
        name = " ".join(contact.split())
        if name:
            names = "|".join(re.escape(part) for part in dict.fromkeys((name, *name.split())))
            address = rf"(?:{address})(?:\s+(?:{names}))?|{names}"
    prefix = rf"^(?:hello|hi|good (?:morning|afternoon|evening))(?:[ ,]+(?:{address}))?(?:[.!?,…]+\s*|\s*$)"
    remaining = re.sub(prefix, "", reply, count=1, flags=re.I)
    if remaining != reply and remaining:
        return remaining[0].upper() + remaining[1:]
    return remaining
