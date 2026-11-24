"""Team 12 (Youssef) · French text → what the voice reads (used by the ElevenLabs client before synthesis)."""

import re

# team 12 (Youssef): what the TTS should READ. The voice mispronounced codes and symbols (« T55 », « 82 % », « 8,46 € »,
# « kg », « AOP ») — the model writes them, the voice needs words. Applied to each sentence just before synthesis.
_TTS_RULES = [
    (re.compile(r"(\d+),(\d{2})\s?(?:€|euros?\b)"), r"\1 euros \2"),  # 8,46 € / 18,50 euros → 8 euros 46
    (re.compile(r"(\d+)\s?€"), r"\1 euros"),
    (re.compile(r"€"), "euros"),
    (re.compile(r"(\d+(?:,\d+)?)\s?%"), r"\1 pour cent"),
    (re.compile(r"(\d+),(\d+)"), r"\1 virgule \2"),
    (re.compile(r"(\d)\s?kg\b", re.I), r"\1 kilos"),
    (re.compile(r"(\d)\s?g\b"), r"\1 grammes"),
    (re.compile(r"(\d)\s?L\b"), r"\1 litres"),
    (re.compile(r"(\d)\s?[×x]\s?(\d)"), r"\1 fois \2"),
    (re.compile(r"\bHT\b"), "hors taxes"),
    (re.compile(r"\bTTC\b"), "toutes taxes comprises"),
    (re.compile(r"\bn°\s?", re.I), "numéro "),
    (re.compile(r"\b(AOP|UHT|BL|TVA|DLC|SAV)\b"), lambda m: " ".join(m.group(1))),
    (re.compile(r"\b([A-Z])(\d{2,3})\b"), r"\1 \2"),  # T55 → T 55 (« té cinquante-cinq »)
]


def tts_text(sentence: str) -> str:
    """The sentence as the voice should read it: « 2 cartons de T55 à 8,46 € HT, 82 % AOP » →
    « 2 cartons de T 55 à 8 euros 46 hors taxes, 82 pour cent A O P »."""
    for rx, rep in _TTS_RULES:
        sentence = rx.sub(rep, sentence)
    return re.sub(r"\s{2,}", " ", sentence)
