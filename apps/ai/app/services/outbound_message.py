"""
Team 12 (Youssef) · the voice message Lucie leaves when her outbound call is not answered (TEAM_OUTBOUND_DEMO).

Same ways of speaking as the live calls:
  - the facts come from the ERP (the attempt's verified offer, the client card), the price sentence from the same code
    as the calls (rules_order.fr_money): the model never computes;
  - the fast model (TEAM_FAST_MODEL) only words it, with Lucie's rules (spoken French, short, warm, one invitation);
  - checked in code: every number it says must be in the facts, else a fixed sentence in the same style is said;
  - said with the call's voice (the TTS client normalises €, %, kg like in the calls: clients/french_speech).
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import date

from app.agent.rules_order import MONTHS_FR, fr_money
from app.clients.base import LLMRequest, LLMText
from app.schemas import ChatMessage
from app.services.voice_reply import spoken_reply

VOICEMAIL_RULES = """Tu es Lucie, l'assistante vocale du Fournil Occitan, grossiste en fournitures de boulangerie à Toulouse.
Tu as appelé un client pour lui proposer une offre ; il n'a pas décroché : tu laisses un message sur son répondeur.
Écris exactement ce que tu dis, en français parlé, chaleureux et naturel, comme une commerciale qui connaît bien ce client :
- 3 phrases courtes au plus (moins de 20 secondes à dire) ;
- commence par « Bonjour <prénom>, c'est Lucie du Fournil Occitan. » ;
- dis pourquoi tu appelles en le reliant à ce qu'il achète (« le beurre de tourage que vous prenez souvent ») ;
- donne le prix et la date de fin exactement comme écrits dans les faits ;
- une seule invitation simple : rappeler, ou répondre à ce message, et on prépare ça avec lui ;
- termine par une formule courte (« Belle journée ! » ou « À bientôt ! ») ;
- n'invente rien : aucun chiffre, date, produit, quantité ou condition qui ne soit pas dans les faits ; pas de liste,
  pas d'emoji, pas de guillemets, aucune note sur toi-même : seulement le message."""
MODEL_TIMEOUT_S = 6
UNTIL = "jusqu'au"


def facts_of(attempt: dict, contact_name: str | None) -> dict:
    offer = attempt["offer"]
    product = offer["productName"].split(" (")[0]
    unit = {"kg": "kilo", "liter": "litre", "l": "litre"}.get(offer.get("unit"), "")
    facts = {
        "prénom": (contact_name or "").split()[0] if contact_name else None,
        "établissement": attempt.get("clientName"),
        "produit": product[:1].lower() + product[1:],
        "achats récents de ce produit": offer.get("purchaseCount") or None,
        "type d'offre": "promotion" if offer.get("kind") == "promo" else "nouveauté",
        "prix hors taxes": f"{fr_money(offer['unitPrice'])} le {unit}" if unit else fr_money(offer["unitPrice"]),
    }
    if offer.get("validUntil"):
        d = date.fromisoformat(offer["validUntil"])
        facts[UNTIL] = f"{d.day} {MONTHS_FR[d.month - 1]}"
    return {k: v for k, v in facts.items() if v}


def template(facts: dict) -> str:
    hello = f"Bonjour {facts['prénom']}" if facts.get("prénom") else "Bonjour"
    why = (f"le {facts['produit']} que vous prenez souvent est en promotion à {facts['prix hors taxes']} hors taxes"
           + (f", jusqu'au {facts[UNTIL]}" if facts.get(UNTIL) else "")) if facts.get("type d'offre") == "promotion" \
        else f"on a une nouveauté qui devrait vous plaire : {facts['produit']}, à {facts['prix hors taxes']} hors taxes"
    return (f"{hello}, c'est Lucie du Fournil Occitan. Je vous appelais parce que {why}. "
            "Si ça vous intéresse, rappelez-nous ou répondez simplement à ce message, et on prépare ça avec vous. Belle journée !")


def _numbers(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def acceptable(text: str, facts: dict) -> bool:
    """Short, starts like a voice message, and every number said is one of the facts' numbers (nothing invented)."""
    allowed = _numbers(json.dumps(facts, ensure_ascii=False))
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]
    return (text.startswith("Bonjour") and len(text) <= 480 and len(sentences) <= 5
            and _numbers(text) <= allowed and "Lucie" in text)


async def compose(facts: dict, llm_factory=None) -> tuple[str, str]:
    """(text, "modèle" | "gabarit"): the fast model's wording if it passes the checks, else the fixed sentence."""
    if llm_factory is None:
        from app.agent.orchestrator import get_fast_llm_client as llm_factory
    try:
        llm = llm_factory()
        req = LLMRequest(system=VOICEMAIL_RULES, messages=[ChatMessage(role="user", content="Faits : " + json.dumps(facts, ensure_ascii=False))],
                         max_tokens=300)  # fmt: skip
        async with asyncio.timeout(MODEL_TIMEOUT_S):
            text = "".join([e.delta async for e in llm.stream(req) if isinstance(e, LLMText)])
        text = re.sub(r"\s+", " ", spoken_reply(text)).strip().strip("«»\"").strip()
        if acceptable(text, facts):
            return text, "modèle"
        print(f"[voicemail] texte du modèle refusé (chiffre inventé ou trop long) : {text[:160]}", flush=True)
    except Exception as e:  # no fast model, timeout, provider down: the fixed sentence
        print(f"[voicemail] modèle indisponible ({type(e).__name__}) : gabarit", flush=True)
    return template(facts), "gabarit"
