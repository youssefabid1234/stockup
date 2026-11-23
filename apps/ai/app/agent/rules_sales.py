"""
OWNER: Daycem · switch TEAM_SALES_RULES · contract: docs/team/interfaces.md §5

« Le bon vendeur » : the agent knows each client's preferences and sells like the best sales rep, without ever
forcing a substitution. Real life: Lucie knows Nadine (Maison Sarrailh) only wants AOP tourage and that Guy
"prefers to run out rather than use standard tourage" → she does NOT push the substitute; for another client who
accepts it, she explains why the 82 % tourage is a good deal (price, promo, works for croissants) and asks.

Two parts:
  1. SALES_RULES: text added to the system prompt (voice + chat) when the switch is on.
  2. Helpers to choose and argue an alternative (used by tools/product_insight.py from Youssef, see interfaces §5).

Sources: client sheets (data/context/clients/*.md: « Ce qui les agace », « Comment leur parler », préférences),
04-playbook-clients.md (« Substitutions : jamais sans accord »), 05-prix-et-credit.md (remises : le standard ne peut
pas en accorder), price rules (GET /api/price-rules).
"""

from __future__ import annotations

from app import team_flags

# TODO(Daycem): write the rules. Starting points to rewrite / test:
#   - Avant de proposer un remplaçant, lire les préférences du client (fiche préchargée) : s'il refuse les
#     substitutions sur ce produit, NE PAS en proposer ; annoncer la rupture et la date de retour.
#   - Sinon : proposer UN remplaçant, dire pourquoi il convient (usage, qualité) et l'avantage prix / promo
#     (get_price ou product_insight), puis demander l'accord. Jamais de substitution sans « oui ».
#   - Pas de remise accordée au téléphone (seul Bernard au-delà de 5 %) : proposer de transmettre.
#   - Ton : suivre la fiche (tutoiement, accent, « appeler Nadine pas Guy »), phrases courtes, chiffres à l'oral.
SALES_RULES = ""


def sales_rules_section() -> str:
    """What prompts.py adds to the system prompt. '' when the switch is off or the rules are empty."""
    return SALES_RULES.strip() if team_flags.sales_rules() else ""


def refuses_substitution(preferences: str, product_name: str) -> bool:
    """
    True if the client's preferences forbid substituting this product (e.g. "Jamais de substitution sur le beurre").
    TODO(Daycem): implement + tests (tests/test_rules_sales.py). Simple keyword rules first; Jev can decide yes/no
    if text is ambiguous (clients/jev.py).
    """
    raise NotImplementedError


def rank_alternatives(alternatives: list[dict], preferences: str) -> list[dict]:
    """
    Order substitutes from best to worst for this client: in stock first, then compatible with preferences, then
    best price / active promo. Each dict: {id, name, unit, price, available, clientPrice?, promo?}.
    TODO(Daycem): implement + tests.
    """
    raise NotImplementedError
