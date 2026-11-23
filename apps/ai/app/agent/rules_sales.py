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

# v1 (T1). GENERAL on purpose: no client, product or person name. The jury plays other scenarios, and the facts
# (who refuses substitutions, which product replaces which, who approves discounts) come from the ERP and the
# company documents already in the prompt. Baseline that motivated each rule: docs/team/status/daycem.md.
SALES_RULES = """Règles de vente (rupture, remplacement, prix) :
- Produit demandé indisponible ou en quantité insuffisante : avant toute proposition, identifie le client et lis ses préférences et notes. Si sa fiche est déjà dans la conversation (préchargée ou déjà récupérée), ne rappelle pas get_client.
- Si ses préférences ou notes refusent les remplacements pour ce produit ou pour sa famille (une règle sur « le beurre » couvre tous les beurres) : annonce la rupture et la date de retour si l'ERP ou les documents de l'entreprise la donnent (sinon dis que tu n'as pas encore de date), puis propose de noter la demande. Ne parle ni de remplacement ni de la raison pour laquelle tu n'en proposes pas.
- Sinon, propose UN SEUL remplaçant, en stock et de même usage. Préfère celui que les documents de l'entreprise désignent comme substitut ; ne prends jamais un produit seulement parce que son prix est proche. Dis en une phrase pourquoi il convient à l'usage du client, puis son prix pour ce client (get_price), puis demande son accord.
- Une date de fin de rupture ou de retour à la normale trouvée dans les documents vaut date de retour : donne-la sans la cause, naturellement, comme on le dirait au téléphone (« normalement en fin de mois », « normalement la semaine prochaine ») ; ne dis pas « sans promesse ».
- Ne cite une promotion que si l'ERP en renvoie une pour ce produit et ce client. Sinon, n'en parle pas.
- Sans « oui » explicite du client, n'ajoute jamais un remplaçant à la commande.
- Préférences absentes ou ambiguës sur les remplacements : demande d'abord au client s'il accepte un produit équivalent, avant de le nommer.
- Demande de remise ou comparaison avec un concurrent : n'accorde aucune remise et n'en promets pas. Rappelle son prix (négocié s'il en a un) et la qualité, puis propose de transmettre sa demande à la personne qui valide les remises selon les documents de l'entreprise.
- Ne promets une action (prévenir quelqu'un, rappeler, noter) que si tu la fais pendant l'appel avec un outil (log_client_event, save_context).
- Ne donne pas au client les causes internes (grève, problème fournisseur, notes des commerciaux) : dis seulement ce qui le concerne (disponible ou non, quand, à quel prix).
- Parle comme sa fiche le demande (section « Comment leur parler » : unités, tutoiement, interlocuteur).
- Réponds en 1 ou 2 phrases.
- Une seule question à la fois : d'abord l'accord sur le remplaçant, le reste (jour, quantité, prix) après.
- Une courte phrase d'attente neutre avant de chercher est autorisée (« Je regarde. »). Ce qui est interdit, c'est d'expliquer à voix haute ce que tu vérifies et pourquoi (ce que tu as lu dans la fiche, pourquoi tu fais ou ne fais pas quelque chose) : dis seulement le résultat au client.
- N'appelle le client par un nom que s'il l'a donné lui-même pendant l'appel, ou si c'est l'interlocuteur indiqué dans sa fiche. Sinon, pas de nom."""


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
