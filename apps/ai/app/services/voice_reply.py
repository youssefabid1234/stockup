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


# team 12 (Youssef, natural voice): one question per reply, and never the same validation question twice in a call.
# Measured: « Je vous mets la crème 35 % ? Vous en voulez combien ? » (two questions) and « On part là-dessus ? » said
# twice in four replies, although the prompt forbids both (natural_rules_test R02, R04, 24/11).
_SENTENCES = re.compile(r"[^.!?…]+[.!?…]+|[^.!?…]+$")


def one_question(reply: str) -> str:
    """Keep only the LAST question: earlier ones become statements (« …35 % ? Vous en voulez combien ? » →
    « …35 %. Vous en voulez combien ? »), so the caller has one thing to answer."""
    parts = _SENTENCES.findall(reply or "")
    asks = [i for i, s in enumerate(parts) if s.rstrip().endswith("?")]
    if len(asks) <= 1:
        return reply
    for i in asks[:-1]:
        parts[i] = re.sub(r"\s*\?+\s*$", ". ", parts[i].rstrip()) if parts[i].rstrip() else parts[i]
    return re.sub(r"\s{2,}", " ", "".join(parts)).strip()


_ASK_FILLER = {"vous", "pour", "c'est", "est-ce", "votre", "vos", "voulez", "avez", "faut", "quel", "quelle", "les", "des",
               "une", "par", "que", "qui", "plutôt", "plutot", "aussi", "alors", "donc", "bien", "est"}


def asked_questions(reply: str | None) -> list[str]:
    """Every question of a reply, as written by the model (one_question later keeps only the last one)."""
    return [s.strip() for s in _SENTENCES.findall(reply or "") if s.rstrip().endswith("?")]


def _question_words(reply: str | None) -> set[str]:
    asks = asked_questions(reply)
    return {w for w in _key(asks[-1]).split() if len(w) >= 3 and w not in _ASK_FILLER} if asks else set()


def without_repeated_question(reply: str, previous: str | list[str] | None) -> str:
    """Team 12 (Youssef), new clients: the question of the previous reply asked again (« Pour le beurre, c'est du tourage
    ou du doux ? » after the caller let it go) is dropped, the rest is said. Measured in new_client_test N2/N5 (24/11):
    asked twice although the prompt says once (the caller's request is already noted « à préciser »)."""
    now = _question_words(reply)
    # previous: the questions asked in the previous reply (all of them), or that reply's text
    befores = [_question_words(q) for q in previous] if isinstance(previous, list) else [_question_words(previous)]
    # the same question reworded (« …tourage ou du doux, et en quelle quantité ? » → « …en tourage ou en doux ? »)
    if not now or not any(b and len(now & b) / min(len(now), len(b)) >= 0.6 for b in befores):
        return reply
    parts = _SENTENCES.findall(reply)
    kept = "".join(p for p in parts if not p.rstrip().endswith("?")).strip()
    return kept or reply


CLOSINGS = ["Je valide ?", "On part là-dessus ?", "C'est bon pour vous ?", "Je vous la confirme ?", "Ça vous va ?",
            "Je la passe comme ça ?", "On valide ?"]
_CLOSING_WORDS = re.compile(r"\b(valide\w*|confirme\w*|part là-dessus|bon pour vous|ça vous va|passe comme ça)\b", re.I)


def _key(s: str) -> str:
    return re.sub(r"[^a-zàâçéèêëîïôûùüÿœ' ]", "", s.lower().replace("’", "'")).strip()


def vary_closing(reply: str, used: list[str]) -> str:
    """If the reply ends with a validation question already asked in this call, swap it for one not used yet.
    `used` (the call's list) is updated with the closing finally said."""
    parts = _SENTENCES.findall(reply or "")
    if not parts:
        return reply
    last = parts[-1].strip()
    if not (last.endswith("?") and len(last) <= 40 and _CLOSING_WORDS.search(last)):
        return reply
    if _key(last) in used:
        fresh = next((c for c in CLOSINGS if _key(c) not in used), None)
        if fresh:
            parts[-1] = (" " if len(parts) > 1 else "") + fresh
            last = fresh
    used.append(_key(last))
    return "".join(parts).strip()


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
    greeting = r"(?:re-?bonjour|bonjour|bonsoir|salut|coucou|hello|allô|allo)"  # team 12: « Salut. » repeated (24/11)
    prefix = rf"^{greeting}(?:[ ,]+(?:{address}))?(?:\s*[.!?,…]+\s*|\s*$)"  # « Madame ! » (French space)
    remaining = re.sub(prefix, "", reply, count=1, flags=re.I)
    if remaining != reply and remaining:
        return remaining[0].upper() + remaining[1:]
    return remaining


# team 12 (Amine K., vitesse) : la réponse est dite PENDANT que le modèle l'écrit. Avant, le lecteur attendait le
# texte complet (Sonnet : 0,3 à 1 s d'écriture après le premier mot). Une phrase est dite dès que la suivante commence ;
# une question attend la fin (one_question / vary_closing la retouchent) ; un texte suivi d'un appel d'outil n'est
# jamais final (une phrase pas encore dite est jetée) ; à la fin, seul le reste de la réponse retouchée est dit.
# a period inside a number or a word (« 8.46 ») is not the end of a sentence: an end mark must be followed by a space
_EARLY_SENTENCE = re.compile(r"\s*((?:[^.!?…]|[.!?…](?=\S))+[.!?…]+)\s+(?=\S)")
_EARLY_SPLIT = re.compile(r"(?:[^.!?…]|[.!?…](?=\S))+(?:[.!?…]+|$)")


class EarlySpeech:
    def __init__(self, say, first):
        self.say, self.first = say, first  # say(sentence) ; first(sentence) -> sentence (salutation, ouverture variée)
        self.step = ""  # texte de l'étape en cours du modèle
        self.said: list[str] = []  # phrases déjà dites dans cette étape
        self.any_said = False
        self.off = False

    def text(self, delta: str) -> None:
        if self.off:
            return
        self.step += delta
        while (m := _EARLY_SENTENCE.match(self.step)) and not m.group(1).rstrip().endswith("?"):
            self.step = self.step[m.end():]
            sentence = without_codes(m.group(1).strip())
            if not self.any_said:
                if _INTERNAL_LEAD.match(sentence):  # une note interne : rien en avance pour ce tour
                    self.off = True
                    return
                sentence = self.first(sentence)
            if sentence.strip():
                self.said.append(sentence)
                self.any_said = True
                self.say(sentence)

    def tool_call(self) -> None:
        self.step, self.said = "", []

    def rest(self, final: str) -> str:
        """Ce qui reste à dire de la réponse finale retouchée (les phrases déjà dites sont sautées)."""
        if not self.said:
            return final
        parts = [p.strip() for p in _EARLY_SPLIT.findall(final or "") if p.strip()]
        return " ".join(parts[len(self.said):])
