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

import re
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app import team_flags
from app.config import settings

# v1 (T1). GENERAL on purpose: no client, product or person name. The jury plays other scenarios, and the facts
# (who refuses substitutions, which product replaces which, who approves discounts) come from the ERP and the
# company documents already in the prompt. Baseline that motivated each rule: docs/team/status/daycem.md.
SALES_RULES = """Règles de vente (rupture, remplacement, prix) :
- Produit demandé indisponible ou en quantité insuffisante : avant toute proposition, identifie le client et lis ses préférences et notes. Si sa fiche est déjà dans la conversation (préchargée ou déjà récupérée), ne rappelle pas get_client.
- Si ses préférences ou notes refusent les remplacements pour ce produit ou pour sa famille (une règle sur « le beurre » couvre tous les beurres) :
  - annonce la rupture et la date de retour telle qu'elle est écrite dans l'ERP ou les documents (sinon dis que tu n'as pas encore de date) ;
  - cherche ensuite une solution qui n'est pas un autre produit : une allocation ou une réservation déjà notée pour ce client sur ce produit (cite la quantité et la période telles qu'elles sont écrites), ou un arrivage attendu dans le stock (get_product_stock) ;
  - propose de noter sa demande pour le premier arrivage seulement si tu peux l'enregistrer avec un outil (log_client_event, type special_request, avec le produit, la quantité et la date souhaitée) ; présente-la comme une demande notée, jamais comme une réservation ou une livraison garantie ;
  - ne parle d'aucun autre produit, ni de la raison pour laquelle tu n'en proposes pas ;
  - même avec tous ces éléments, 2 phrases maximum : garde les plus utiles au client.
- Si ce client demande lui-même une alternative : propose le remplaçant (même usage, en stock) en disant clairement la différence avec le produit demandé (qualité, composition, prix), puis demande son accord. Sans « oui », rien n'est ajouté.
- Sinon, propose UN SEUL remplaçant, en stock et de même usage. Préfère celui que les documents de l'entreprise désignent comme substitut ; ne prends jamais un produit seulement parce que son prix est proche. Dis en une phrase pourquoi il convient à l'usage du client, puis son prix pour ce client (get_price), puis demande son accord.
- Une date de fin de rupture ou de retour à la normale trouvée dans les documents vaut date de retour : donne-la telle qu'elle est écrite, sans la transformer ni en déduire une autre (si le document dit « jusqu'à la fin du mois », dis « normalement fin du mois », pas « début du mois prochain »). Sans la cause, et ne dis pas « sans promesse ».
- Ne cite une promotion que si l'ERP en renvoie une pour ce produit et ce client. Sinon, n'en parle pas.
- Sans « oui » explicite du client, n'ajoute jamais un remplaçant à la commande.
- Préférences absentes ou ambiguës sur les remplacements : demande d'abord au client s'il accepte un produit équivalent, avant de le nommer.
- Demande de remise ou comparaison avec un concurrent : tu n'accordes et ne promets aucune remise. Dis son prix (négocié s'il en a un, get_price), puis la valeur du produit en une phrase (qualité, origine, telles que les documents les décrivent). Si la demande dépasse ce qu'un commercial peut accorder selon les documents de l'entreprise, propose de la transmettre à la personne qui valide ces remises (nommée dans les documents), pas au commercial ; sinon, à son commercial. N'ajoute aucun mot qui engage (« garanti », « il validera », « ça devrait passer ») : dis seulement que cette personne décidera.
- Ne promets une action (prévenir quelqu'un, rappeler, noter) que si tu la fais pendant l'appel avec un outil (log_client_event, save_context).
- Les notes internes restent privées : ne donne pas au client les causes (grève, problème fournisseur) ni les avis de l'équipe. Les faits qui le concernent directement peuvent lui être dits (disponible ou non, quand, à quel prix, une allocation ou une réservation déjà notée pour lui).
- Parle comme sa fiche le demande (section « Comment leur parler » : unités, tutoiement, interlocuteur).
- Réponds en 1 ou 2 phrases.
- Une seule question à la fois : d'abord l'accord sur le remplaçant, le reste (jour, quantité, prix) après.
- Une courte phrase d'attente neutre avant de chercher est autorisée (« Je regarde. »). Ce qui est interdit, c'est d'expliquer à voix haute ce que tu vérifies et pourquoi (ce que tu as lu dans la fiche, pourquoi tu fais ou ne fais pas quelque chose) : dis seulement le résultat au client.
- N'appelle le client par un nom que s'il l'a donné lui-même pendant l'appel, ou si c'est l'interlocuteur indiqué dans sa fiche. Sinon, pas de nom."""


def sales_rules_section() -> str:
    """What prompts.py adds to the system prompt. '' when the switch is off or the rules are empty."""
    return SALES_RULES.strip() if team_flags.sales_rules() else ""


# ── T3 · does this client accept a substitute for this product? ──────────────────────────────────────────────────
#
# Keywords first: 92 of the 104 cards carry a ready-made sentence (« Refuse / Accepte les substitutions »), read here
# without any model. Jev only when no sentence is found (measured: 5-6/10 alone, ~150 ms; see
# docs/team/jev-substitution-test.md). Whatever the answer, "accepte" only means "you may PROPOSE one substitute":
# the caller's explicit yes is still required before adding it (SALES_RULES, and substitute_for in add_order_line).

Policy = Literal["refuse", "accepte", "demander", "inconnu"]

# "refuse ... substitution(s)", "jamais de substitution", "aucune substitution", "ne jamais substituer"
_REFUSAL = re.compile(
    r"(refuse (?:les |toute |toutes les )?substitutions?|jamais de substitutions?|aucune substitution"
    r"|ne (?:jamais )?substitue[rz]?|jamais substituer)(?P<rest>[^.;:]*)"
)
_ACCEPT = re.compile(r"accepte (?:les |des )?substitutions?")
# "... sans être prévenu / sans accord / si on prévient" turns a refusal into "yes, if we ask first": on the phone we do.
_WITH_NOTICE = re.compile(r"\b(sans (?:etre |l')?(?:prevenu|prevenir|accord|son accord)|si on (?:le )?previent)\b")
_SCOPE = re.compile(r"^\s*(?:sur\s+)?(?:(?:le|la|les|un|une|des|du|de)\s+|l')([a-z]+)")
# words that say nothing about which product it is
_GENERIC = {
    "de", "du", "des", "la", "le", "les", "et", "en", "au", "aux", "pour", "avec", "sans", "plaque", "plaques", "carton",
    "cartons", "sac", "sacs", "kg", "brique", "motte", "piece", "pieces", "lot", "boite", "pot", "seau", "bidon",
}  # fmt: skip


def _norm(text: str) -> str:
    """Lowercase, no accents, so « Être prévenu » and « etre prevenu » compare the same."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", _norm(text)) if len(w) > 1 and w not in _GENERIC}


def _applies_to(scope: str | None, product_words: set[str]) -> bool:
    """A sentence scoped to « le beurre » applies to « Beurre de tourage … »; no scope = every product."""
    return scope is None or scope in product_words or scope.rstrip("s") in product_words


def _names_product(preferences: str, product_words: set[str]) -> bool:
    """Do the preferences name THIS product as their choice (e.g. « Tourage AOP pour la viennoiserie »)?
    Two distinctive words of the product in one clause."""
    return any(len(_words(clause) & product_words) >= 2 for clause in re.split(r"[.;,]", preferences or ""))


def substitution_policy(product_name: str, preferences: str, notes: list[str] | tuple[str, ...] = ()) -> Policy:
    """
    What the card says about substituting this product, from keywords only (no model, no network):
      "refuse"   a refusal that applies to this product (preferences or notes): announce the shortage, no other product
      "accepte"  substitutes accepted (at least if we tell them): propose ONE, then ask for a yes
      "demander" accepted in general, but the preferences name this very product: ask before naming a substitute
      "inconnu"  nothing usable: let Jev decide (decide_substitution), or ask
    A refusal in the preferences wins over a softer note.
    """
    product_words = _words(product_name)
    accepted = False
    for text in [preferences, *notes]:
        for m in _REFUSAL.finditer(_norm(text)):
            rest = m.group("rest")
            notice = _WITH_NOTICE.search(rest)
            scope = _SCOPE.match(_WITH_NOTICE.sub("", rest))
            if not _applies_to(scope.group(1) if scope else None, product_words):
                continue
            if notice:
                accepted = True
            else:
                return "refuse"
        if _ACCEPT.search(_norm(text)):
            accepted = True
    if not accepted:
        return "inconnu"
    return "demander" if _names_product(preferences, product_words) else "accepte"


def refuses_substitution(preferences: str, product_name: str) -> bool:
    """True if the client's preferences forbid substituting this product (e.g. "Jamais de substitution sur le beurre").
    Contract of interfaces.md §5 (product_insight). Keywords only; « demander » is not a refusal."""
    return substitution_policy(product_name, preferences) == "refuse"


JEV_YES, JEV_NO = 0.8, 0.2  # below / above: too unsure, ask the caller (thresholds of the measured test)


async def decide_substitution(
    product_name: str,
    preferences: str,
    notes: list[str] | tuple[str, ...] = (),
    profile: str = "",
    jev=None,  # clients.jev.JevClient, or None (no key): then "demander"
) -> Literal["refuse", "accepte", "demander"]:
    """Keywords first; Jev only when the card has no usable sentence; any doubt or error → "demander"."""
    policy = substitution_policy(product_name, preferences, notes)
    if policy != "inconnu":
        return policy
    if jev is None:
        return "demander"
    state = {"preferences": preferences, "notes": list(notes), **({"profil": profile} if profile else {})}
    try:
        p = await jev.yes_no(
            state,
            f"Ce client accepte-t-il un autre produit à la place de « {product_name} », quand celui-ci manque ?",
            "La fiche dit qu'il accepte les remplacements pour ce produit, au moins s'il est prévenu.",
            "La fiche dit qu'il refuse les remplacements (en général ou sur ce produit).",
        )
    except Exception:  # Jev down / slow: never block a voice turn on it
        return "demander"
    return "accepte" if p >= JEV_YES else "refuse" if p <= JEV_NO else "demander"


# ── T3 · rank_alternatives: the substitute the company itself names comes first ─────────────────────────────────
#
# The ERP's /alternatives sorts by closest price (for the AOP tourage: salted butter first, the 82 % tourage third).
# The company docs say which product replaces which (« Substitutions habituelles », `Produit (prd_X) → Remplaçant
# (prd_Y)`): read from DATA_DIR/context, so no product name lives in the code and any data pack works.

def doc_substitutes(folder: Path | None = None) -> dict[str, list[str]]:
    """{product id: [substitute ids, in the docs' order]} from every Markdown file of the context folder.
    {} if the folder is missing. Cached per folder (the docs don't change during a call)."""
    return dict(_read_substitutes(str(folder or settings.data_dir / "context")))


@lru_cache(maxsize=4)
def _read_substitutes(folder: str) -> tuple[tuple[str, list[str]], ...]:
    found: dict[str, list[str]] = {}
    try:
        files = sorted(p for p in Path(folder).iterdir() if p.name.endswith(".md"))
    except OSError:
        return ()
    for path in files:
        for line in path.read_text(encoding="utf-8").splitlines():
            if "→" not in line:
                continue
            ids = re.findall(r"\((prd_[\w-]+)\)", line)
            if len(ids) >= 2 and line.index(f"({ids[0]})") < line.index("→") < line.index(f"({ids[-1]})"):
                found.setdefault(ids[0], [])
                if ids[-1] not in found[ids[0]]:
                    found[ids[0]].append(ids[-1])
    return tuple(found.items())


def rank_alternatives(
    alternatives: list[dict],
    preferences: str,  # kept for the interfaces.md §5 contract; refusing is decide_substitution's job, not ranking's
    *,
    for_product_id: str | None = None,  # the missing product: to find its substitute in the docs
    for_category: str | None = None,  # its category: "same use"
    substitutes: dict[str, list[str]] | None = None,  # default: read from the docs (doc_substitutes)
) -> list[dict]:
    """
    Order substitutes from best to worst. Never drops or changes one (the agent proposes the first, with consent):
      1. in stock (available > 0)        2. named as substitute in the company docs
      3. same category (same use)        4. active promo            5. then the ERP's own order
    Each dict: {id, name, unit, price, available, clientPrice?, promo?, category?} (product_insight / find_alternatives).
    """
    if substitutes is None:
        substitutes = doc_substitutes() if for_product_id else {}
    named = substitutes.get(for_product_id or "", [])

    def key(item: tuple[int, dict]) -> tuple:
        position, alt = item
        doc_rank = named.index(alt.get("id")) if alt.get("id") in named else len(named)
        return (
            not (alt.get("available") or 0) > 0,
            doc_rank,
            not (for_category and alt.get("category") == for_category),
            not alt.get("promo"),
            position,
        )

    return [alt for _, alt in sorted(enumerate(alternatives), key=key)]
