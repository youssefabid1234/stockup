"""
OWNER: Amine Khalil · switch TEAM_ORDER_RULES · contract: docs/team/interfaces.md §4

« La commande juste » : what the agent must understand and check so that the order in the ERP is exactly what the
caller meant. Real life: Lucie knows "10 de tradi" = 10 sacks of 25 kg, "comme d'hab" = the usual basket, never
confirms without reading the order back, never promises anything to a blocked client.

Two parts:
  1. ORDER_RULES: text added to the system prompt (voice + chat modes) when the switch is on.
  2. Deterministic helpers (quantities, units, dates): the brief says "du code déterministe pour ce qui n'a pas
     besoin d'un modèle". Faster and never wrong. Business rules that touch prices / stock / credit stay in the
     backend (AGENTS.md): read the ERP's order warnings (client_blocked, no_route…) instead of re-coding them.

Sources to read first: data/context/01-entreprise.md (« Règles de la maison »), 02-journee-type.md (heures limites),
03-glossaire-produits.md (« On dit »), 04-playbook-clients.md (« Prendre une commande »), ERP.md (order lifecycle).
"""

from __future__ import annotations

from datetime import date

from app import team_flags

# TODO(Amine K.): write the rules. Keep them short and imperative: the model re-reads them at every step.
# Starting points (from the data pack), to rewrite / complete / test:
#   - Farines au sac de 25 kg (épeautre 10 kg) : « 10 de tradi » = 10 sacs de T55 tradition, jamais 10 kg.
#   - « Chocolatine » = pain au chocolat : ne jamais corriger le client.
#   - « Comme d'hab » : partir de la commande habituelle (fiche client), la dire, faire préciser les quantités.
#   - Changement d'avis (« finalement pas de… », « mets plutôt… ») : modifier la ligne, ne pas en ajouter une.
#   - Relire produits, quantités (dites à l'oral) et jour de livraison AVANT confirm_order ; attendre un oui.
#   - Compte bloqué : ne rien promettre, prendre le message pour la comptabilité.
#   - Jamais de livraison un jour où le client n'est pas livré / fermé ; commande avant 17h pour le lendemain.
#   - Franco 150 € HT, sinon 12 € de livraison : le dire si la commande est petite.
ORDER_RULES = ""


def order_rules_section() -> str:
    """What prompts.py adds to the system prompt. '' when the switch is off or the rules are empty."""
    return ORDER_RULES.strip() if team_flags.order_rules() else ""


# ── Deterministic helpers (TODO(Amine K.)): pure functions, unit-tested in tests/test_rules_order.py ──


def next_delivery_date(today: date, delivery_days: list[str], asked: str | None = None, now_hour: int = 6) -> date | None:
    """
    The delivery date for "jeudi", "demain", "au plus vite"… given the client's delivery days and the 17h cut-off.
    Use the ERP's business date (GET /api/meta → today), never the real clock.
    TODO(Amine K.): implement + tests. Return None if `asked` is a day the client is not delivered.
    """
    raise NotImplementedError


def sacks_from_words(product_unit: str, qty: float, said_unit: str | None) -> float:
    """
    Convert what was said into the product's selling unit (sacs, plaques, cartons…), e.g. "10 de tradi" → 10 sacks.
    TODO(Amine K.): implement + tests, or decide it is better left to the model with good rules (write why in
    DECISIONS.md).
    """
    raise NotImplementedError
