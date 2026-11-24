"""
OWNER: Youssef · how the agent HEARS the caller (hands-free made robust).

Real life: on the phone people talk in pieces ("I would need to tour... uh... 3 boxes... for Monday, no Tuesday"),
a colleague talks in the background, a word is drowned by the oven fan. Lucie keeps ALL the pieces, answers the whole
request once, ignores the colleague, and asks again for the word she did not catch.

1. merge_parts: every piece said before the agent answered goes to the model as ONE message, in order (the voice
   session keeps them in Conversation.pending; nothing is lost when a new piece interrupts the agent's thinking).
2. annotate: from the STT's final tokens (Soniox: speaker + confidence per token), mark the other voices and the
   "[caller] 3 boxes of turning [other voice] you get a coffee?" or "3 boxes of
   touron(?) ». None when there is nothing to mark (one voice, all words sure): the plain transcript is used.
3. LISTENING_RULES: the voice-mode rule that tells the model how to read the two above.
"""

from __future__ import annotations

DOUBT = 0.5  # a word whose least sure piece is below this confidence is marked « (?) »

LISTENING_RULES = """Listening on the phone:
- Numbered utterances are pieces of one request. Answer once, using the latest correction.
- Use [caller] speech. Ignore [other voice] unless the caller explicitly adopts it.
- A word marked (?) is uncertain. Ask about it if it changes the product, quantity, date or name.
- Ignore incidental background noise. Ask the caller to repeat if the request is unintelligible."""


def listening_section(mode: str) -> str:
    return LISTENING_RULES if mode == "voice" else ""


def merge_parts(parts: list[str]) -> str:
    """The caller's pieces (oldest first) as one user message. One piece = itself, unchanged."""
    parts = [p.strip() for p in parts if p and p.strip()]
    if len(parts) <= 1:
        return parts[0] if parts else ""
    lines = "\n".join(f"{i}. {p}" for i, p in enumerate(parts, 1))
    return f"(The caller spoke in {len(parts)} parts before your reply, in this order:)\n{lines}"


def annotate(tokens: list[dict]) -> str | None:
    """Final STT tokens → transcript with [appelant]/[autre voix] and « mot(?) », or None if nothing to mark.
    A token starting with a space starts a new word (Soniox splits words into pieces). Control tokens (<end>,
    <fin>) are ignored. The caller = the voice that said the most words (ties: the first one heard)."""
    words: list[list] = []  # [text, speaker, lowest confidence]
    for tok in tokens:
        text = tok.get("text") or ""
        if not text or text.startswith("<"):
            continue
        speaker, conf = tok.get("speaker"), tok.get("confidence", 1.0)
        if text.startswith(" ") or not words:
            words.append([text, speaker, conf])
        else:
            words[-1][0] += text
            words[-1][1] = words[-1][1] or speaker
            words[-1][2] = min(words[-1][2], conf)
    if not words:
        return None
    voices = [w[1] for w in words if w[1] is not None]
    main = max(dict.fromkeys(voices), key=voices.count) if voices else None  # dict keeps the first-heard order
    several = len(set(voices)) > 1
    doubtful = any(w[2] < DOUBT and w[0].strip(" .,;:!?…") for w in words)
    if not several and not doubtful:
        return None
    out: list[str] = []
    current = None
    for text, speaker, conf in words:
        word = text.strip()
        core = word.rstrip(".,;:!?…")
        if conf < DOUBT and core:
            word = f"{core}(?){word[len(core):]}"  # the mark before the punctuation: « touron(?). »
        if several:
            who = "caller" if speaker in (main, None) else "other voice"
            if who != current:
                out.append(f"[{who}]")
                current = who
        out.append(word)
    return " ".join(out).replace(" ,", ",").replace(" .", ".")
