"""
OWNER: Youssef · how the agent HEARS the caller (hands-free made robust).

Real life: on the phone people talk in pieces (« il me faudrait du tourage… euh… 3 cartons… pour lundi, non mardi »),
a colleague talks in the background, a word is drowned by the oven fan. Lucie keeps ALL the pieces, answers the whole
request once, ignores the colleague, and asks again for the word she did not catch.

1. merge_parts: every piece said before the agent answered goes to the model as ONE message, in order (the voice
   session keeps them in Conversation.pending; nothing is lost when a new piece interrupts the agent's thinking).
2. annotate: from the STT's final tokens (Soniox: speaker + confidence per token), mark the other voices and the
   doubtful words, e.g. « [appelant] 3 cartons de tourage [autre voix] tu prends un café ? » or « 3 cartons de
   touron(?) ». None when there is nothing to mark (one voice, all words sure): the plain transcript is used.
3. LISTENING_RULES: the voice-mode rule that tells the model how to read the two above.
"""

from __future__ import annotations

DOUBT = 0.5  # a word whose least sure piece is below this confidence is marked « (?) »

LISTENING_RULES = """Écoute (au téléphone) :
- L'appelant peut parler en plusieurs morceaux (il a fait des pauses avant ta réponse) : ils arrivent numérotés dans un seul message. C'est UNE seule demande : réponds à l'ensemble, une seule fois. Si un morceau en corrige un autre (« 10… non 12 », « plutôt mardi »), la dernière correction l'emporte.
- [appelant] et [autre voix] : plusieurs personnes ont été entendues. Ne tiens compte que de l'appelant ; une autre voix (collègue, client en boutique, radio) n'est pas une demande, sauf si l'appelant la reprend à son compte.
- Un mot suivi de (?) a été mal entendu. S'il compte (produit, quantité, date, nom), redemande-le simplement au lieu de deviner ; sinon, ignore-le.
- Bruit ou phrase qui n'a pas de sens pour la commande : n'en fais pas une demande. Si tu n'as rien compris d'utile, demande poliment de répéter.
- Pose des questions fermées (« je l'ajoute à votre livraison de mercredi ? »), jamais « A ou B ? ». Si tu as quand même posé un choix et qu'il répond seulement « oui » ou « non », ne choisis pas à sa place : redemande en une phrase courte.
- Plus de 4 produits à relire (commande habituelle, grosse commande) : n'énumère pas tout au téléphone. Dis le nombre de produits, les 2 ou 3 principaux et le total, puis propose le détail (« je vous détaille ? ») ; détaille si le client le demande. Cette règle prime sur la relecture complète."""


def listening_section(mode: str) -> str:
    return LISTENING_RULES if mode == "voice" else ""


def merge_parts(parts: list[str]) -> str:
    """The caller's pieces (oldest first) as one user message. One piece = itself, unchanged."""
    parts = [p.strip() for p in parts if p and p.strip()]
    if len(parts) <= 1:
        return parts[0] if parts else ""
    lines = "\n".join(f"{i}. {p}" for i, p in enumerate(parts, 1))
    return f"(L'appelant a parlé en {len(parts)} fois avant ta réponse, dans l'ordre :)\n{lines}"


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
            who = "appelant" if speaker in (main, None) else "autre voix"
            if who != current:
                out.append(f"[{who}]")
                current = who
        out.append(word)
    return " ".join(out).replace(" ,", ",").replace(" .", ".")


# ── a real « oui » before confirming (used by confirm_order, tools/order_jev.py) ──

import re as _re
import unicodedata as _ud

_YES = _re.compile(
    r"\b(oui|ouais|ouai|ok|okay|okey|d'?accord|dac|bon|parfait|valide[rz]?|validons|confirme[rz]?|allez|allez-y|vas-y|go|"
    r"ca marche|ca me va|ca roule|ca ira|exact|exactement|tout a fait|c'?est ca|banco|entendu|tres bien|nickel|impeccable|"
    r"super|top|yes|yep|evidemment|bien sur|absolument|carrement|volontiers|mettez|faites|envoyez)\b"
)


def explicit_yes(answer: str) -> bool:
    """Does the caller's reply contain at least one word of agreement? « Pour jeudi », « Vendredi », « Combien ça
    fait ? » → False (a detail or a question, not a yes). Jev still decides the doubtful « oui mais… » afterwards."""
    text = _ud.normalize("NFKD", answer or "").encode("ascii", "ignore").decode().lower().replace("’", "'")
    return bool(_YES.search(text))
