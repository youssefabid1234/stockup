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
SALES_RULES_EN = """Sales rules (shortage, substitute, price):
- Requested product unavailable or not enough of it: before any offer, identify the client and read their preferences and notes. If their card is already in the conversation (preloaded or already fetched), do not call get_client again.
- If their preferences or notes refuse substitutes for this product or its family (a rule about « the butter » covers every butter):
  - announce the shortage and the return date exactly as written in the ERP or the documents (otherwise say you do not have a date yet);
  - then look for a solution that is not another product: an allocation or a reservation already noted for this client on this product (quote the quantity and the period as written), or an expected arrival in stock, as the ERP gives it;
  - offer to note their request for the first arrival only if you can record it with a tool (log_client_event, type special_request, with the product, the quantity and the wished date); present it as a noted request, never as a reservation or a guaranteed delivery;
  - mention no other product, nor why you are not offering one;
  - even with all of this, exactly 2 sentences. Sentence 1: the shortage, with the return date, or else the allocation or arrival that concerns them. Sentence 2: the offer to note their request, as a question. Example of the form: « The [requested product] is out of stock, with no return date yet, but you have [quantity] reserved for [period]. Shall I note your request for the first arrival? »
- If this client asks for an alternative themselves: offer the substitute (same use, in stock) and say clearly how it differs from the requested product (quality, composition, price), then ask for their agreement. Without a « yes », nothing is added.
- Otherwise, offer ONE substitute only, in stock and with the same use. Prefer the one the company documents name as the substitute; never pick a product only because its price is close.
- When the tool says no product in stock has the same use, announce the shortage and ask the client what they would like, without offering any product. Example of what you say: « The [requested product] is out of stock at the moment, and I have nothing equivalent in stock. What would you like to do? »
- First offer of a substitute: exactly 2 sentences.
  - Sentence 1: the shortage and the substitute, with its reason in a few words.
  - Sentence 2: its price for this client as the ERP already gives it (per kilo, per unit or per carton, with the promotion only if the ERP returns one), then the question asking for agreement.
  - Example of the form: « The [requested product] is out of stock, but I have the [substitute], which does the same job. It is [price] a kilo with the promotion until [date]: shall I put it in instead? »
  - Nothing else at that point: no total and no calculation (quote_line comes later for totals), no delivery date, unless the client asks for them or the requested day is not delivered (then the order's date rule applies).
- An end-of-shortage or back-to-normal date found in the documents counts as the return date: give it exactly as written, without changing it or deducing another one (if the document says « until the end of the month », say « normally the end of the month », not « early next month »). Without the cause, and do not say « no promise ».
- Mention a promotion only if the ERP returns one for this product and this client. Otherwise, do not talk about it.
- Without an explicit « yes » from the client, never add a substitute to the order.
- When the card says nothing clear about substitutes for this product, announce the shortage, then ask the client whether they accept an equivalent product, without naming it. Example of what you say: « The [requested product] is out of stock at the moment. Would you accept an equivalent product instead? »
- Discount request or comparison with a competitor: you neither grant nor promise any discount. Give their price as the ERP gives it for this client (negotiated if they have one), then the product's value in one sentence (quality, origin, as the documents describe them). If the request goes beyond what a sales rep may grant according to the company documents, offer to pass it on to the person who approves such discounts (named in the documents), not to the sales rep; otherwise, to their sales rep. Add no committing word (« guaranteed », « he will approve », « it should go through »): only say that this person will decide.
- Promise an action (telling someone, calling back, noting) only if you do it during the call with a tool (log_client_event, save_context).
- Internal notes stay private: do not tell the client the causes (strike, supplier problem) or the team's opinions. Facts that concern them directly may be told (available or not, when, at what price, an allocation or a reservation already noted for them).
- Speak as their card asks (section on how to talk to them: units, formality, contact person).
- Answer in 1 or 2 sentences. A short greeting at the start of the call (« Hello [first name]. ») does not count in these 2 sentences.
- Never say a field name or a technical value returned by a tool (« substitution », « inconnu », « demander », « inStock »…): they are hints for you, not sentences for the client.
- Your answer starts directly with what you say to the client: never a label followed by a colon, nor a note about what you decided.
- One question at a time: first the agreement on the substitute, the rest (day, quantity, total) afterwards.
- Never explain out loud what you are checking and why (what you read on the card, why you do or do not do something): only tell the client the result.
- Call the client by a name only if they gave it themselves during the call, or if it is the contact person on their card. Otherwise, no name."""

SALES_RULES = SALES_RULES_EN


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

# French and English (data/seed_en, SEED_DIR_NAME=seed_en): a card is in one language or the other, no switch needed.
# "refuse ... substitution(s)", "jamais de substitution", "aucune substitution", "ne jamais substituer"
# "refuses substitutions", "substitutions refused", "never any substitution", "does not want any substitution"
_REFUSAL = re.compile(
    r"(refuse (?:les |toute |toutes les )?substitutions?|jamais de substitutions?|aucune substitution"
    r"|ne (?:jamais )?substitue[rz]?|jamais substituer"
    r"|refuses (?:any |all )?substitutions?|substitutions? (?:are |is )?refused|never (?:any )?substitutions?"
    r"|never substitute|no substitutions?|(?:does|do) not (?:want|accept) any substitutions?)(?P<rest>[^.;:]*)"
)
_ACCEPT = re.compile(r"accepte (?:les |des )?substitutions?|accepts? (?:\w+ )?substitutions?|substitutions? (?:are |is )?accepted")
# "... sans être prévenu / sans accord / si on prévient" (« without being told », « if informed ») turns a refusal into
# "yes, if we ask first": on the phone we do.
_WITH_NOTICE = re.compile(
    r"\b(sans (?:etre |l')?(?:prevenu|prevenir|accord|son accord)|si on (?:le )?previent"
    r"|without (?:being )?(?:told|informed|warned|notified)|without (?:his |her |their |prior )?(?:agreement|consent|notice)"
    r"|if (?:we are |he is |she is |they are )?(?:told|informed|warned|notified))\b"
)
_SCOPE = re.compile(r"^\s*(?:(?:sur\s+)?(?:(?:le|la|les|un|une|des|du|de)\s+|l')|(?:on|for)\s+(?:the\s+)?)([a-z]+)")
# words that say nothing about which product it is
_GENERIC = {
    "de", "du", "des", "la", "le", "les", "et", "en", "au", "aux", "pour", "avec", "sans", "plaque", "plaques", "carton",
    "cartons", "sac", "sacs", "kg", "brique", "motte", "piece", "pieces", "lot", "boite", "pot", "seau", "bidon",
    "the", "of", "for", "with", "from", "and", "bag", "sheet", "tub", "tray", "case", "pack", "box", "bottle", "block",
    "packet", "punnet", "size", "container",
}  # fmt: skip


def _norm(text: str) -> str:
    """Lowercase, no accents, so « Être prévenu » and « etre prevenu » compare the same."""
    text = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", text.lower())


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", _norm(text)) if len(w) > 1 and w not in _GENERIC}


def _applies_to(scope: str | None, product_words: set[str]) -> bool:
    """A sentence scoped to « le beurre » / « the butter » applies to every product named so; no scope = every product."""
    return scope is None or scope in product_words or scope.rstrip("s") in product_words


def _names_product(preferences: str, product_words: set[str]) -> bool:
    """Do the preferences name THIS product as their choice (e.g. « Tourage AOP pour la viennoiserie »)?
    Two distinctive words of the product in one clause. (English names use two words for one French one, « laminating
    butter » for « tourage »: a card can then look like it names the product when it names a cousin → « demander »,
    the careful side. Audit: docs/team/t3-ranking-audit.md.)"""
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
            f"Will this customer accept an alternative when {product_name} is unavailable?",
            "The customer accepts replacements for this product, at least with advance notice.",
            "The customer refuses replacements for this product or in general.",
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


# ── T3 · same use, when the docs name no substitute: names that share distinctive words ─────────────────────────────
#
# Audit 24/11 (docs/team/t3-ranking-audit.md): with only the ERP order (closest price), 29 of the 62 products the docs
# don't cover got an absurd first choice for the same use. Product names say the use (first word, then qualifiers):
# compare them, without the packaging (in parentheses), numbers and units. No product name lives in this code.

_NAME_STOP = {"de", "du", "des", "la", "le", "les", "et", "en", "au", "aux", "pour", "avec", "sans", "cm", "mm", "kg",
              "ml", "cl", "g", "l", "x", "un", "une", "ce", "cet", "cette", "ces", "tout", "tous", "on", "il", "elle",
              # English (data/seed_en): small words, and the generic nouns of the cards (« frozen goods »)
              "the", "of", "from", "for", "with", "and", "in", "an", "to", "by", "per", "that", "this", "any", "all",
              "goods", "good", "products", "product", "items", "item"}  # fmt: skip

# English names put the product LAST (« UHT liquid cream 35% »), French names FIRST (« Crème liquide UHT 35 % »).
_EN_MARKERS = re.compile(r"\b(?:of|the|from|with|for|and|only|never|exclusively|does|bag|tub|sheet|tray|case|pack|punnet|"
                         r"packet|bottle|block|container)\b")  # fmt: skip
_FR_MARKERS = re.compile(r"\b(?:de|du|des|la|le|les|aux|au|et|pour|avec|uniquement|jamais|exclusivement|sac|seau|plaque|"
                         r"barquette|colis|lot|brique|bidon|paquet|plateau|bouteille|sachet)\b|\bd'|\bl'")  # fmt: skip
_EN_CUT = re.compile(r"\s(?:of|from|for|with|in)\s")


@lru_cache(maxsize=4)
def _glossary(folder: str) -> dict[str, str]:
    """{English name (normalised): French name} from every DATA_DIR/*/GLOSSARY.md (| `prd_…` | French | English |,
    data/seed_en/GLOSSARY.md by Youssef). Lets an English name be compared word for word like its French original
    (« cream » and « crème » are not the same word). {} if there is none: then the English rules below apply."""
    found: dict[str, str] = {}
    for path in sorted(Path(folder).glob("*/GLOSSARY.md")):
        for fr, en in re.findall(r"^\|\s*`[^`]+`\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$", path.read_text(encoding="utf-8"), re.M):
            found[_norm(en).strip()] = fr
    return found


def _as_french(name: str) -> str:
    """The French original of a glossary name, else the name itself (a French name stays as it is)."""
    return _glossary(str(settings.data_dir)).get(_norm(name or "").strip(), name or "")


def _is_english(text: str) -> bool:
    t = _norm(text)
    return len(_EN_MARKERS.findall(t)) > len(_FR_MARKERS.findall(t))


def _head(text: str, english: bool | None = None) -> str | None:
    """The word that says which product it is: first word in French, last word before « of / from / for… » in English.
    Percentages never are. `english`: the language when the text alone is too short to tell (« 35% cream »)."""
    if _is_english(text) if english is None else english:
        core = _EN_CUT.split(" " + re.sub(r"\([^)]*\)", " ", _norm(text)) + " ", maxsplit=1)[0]
        words = [w for w in _name_words(core) if "%" not in w]
        return words[-1] if words else None
    words = [w for w in _name_words(text) if "%" not in w]
    return words[0] if words else None


def _name_words(name: str, *, percent: bool = False) -> list[str]:
    """Distinctive words of a product name, in order (the first one is usually the product itself).
    « Pommes vertes bio (colis de 12) » → ["pomm", "vert", "bio"]: plural and feminine folded, packaging dropped.
    percent=True keeps « 35 % » as a word "35%" (the card rules: « … 35 % uniquement »)."""
    name = re.sub(r"\([^)]*\)", " ", (name or "").replace("œ", "oe").replace("Œ", "Oe"))
    out = []
    for w in re.findall(r"\d+(?:[.,]\d+)?\s*%|[a-z0-9]+", _norm(name)):
        if "%" in w:
            if percent:
                out.append(re.sub(r"\s+", "", w))
            continue
        if w in _NAME_STOP or w.isdigit() or len(w) < 2:
            continue
        w = w[:-1] if w.endswith("s") and len(w) > 3 else w
        while w.endswith("e") and len(w) > 3:  # « surgelée » and « surgelé » meet
            w = w[:-1]
        out.append(w)
    return out


def name_match(missing_name: str, candidate_name: str, others: list[str] | tuple[str, ...] = ()) -> int:
    """How much a candidate's name says « same use » as the missing product: shared distinctive words, the first word
    of the missing product counting double. A word that most `others` (the candidate list) share decides nothing
    (the family word shared by the whole list). 0 = nothing in common."""
    missing_name, candidate_name = _as_french(missing_name), _as_french(candidate_name)  # English → French original
    missing, cand = _name_words(missing_name), set(_name_words(candidate_name))
    if not missing:
        return 0
    first = _head(missing_name) or missing[0]
    lists = [set(_name_words(_as_french(o))) for o in others]
    common = {w for w in missing if lists and sum(w in o for o in lists) > len(lists) / 2}
    head = 2 if first in cand and first not in common else 0
    return head + len((set(missing) - {first} - common) & cand)


# ── T3 · what the client's card forbids (« jamais de… ») or imposes (« … uniquement ») is never proposed ────────────
#
# Audit 24/11: 29 of the 104 cards say it (« Ne veut pas de surgelé », « Crème 35 % uniquement, jamais d'épaisse »,
# « Farine de tradition du Lauragais uniquement »…). Read by clause, matched on product-name words: a sentence whose
# words are in no product name (« jamais de livraison ce jour-là ») excludes nothing. Substitution sentences stay with
# substitution_policy. Known limits (no synonyms, no supplier/brand): docs/team/t3-ranking-audit.md.

CardRule = tuple[Literal["interdit", "seulement"], str, frozenset[str]]  # kind, first word, words

_FORBID = re.compile(
    r"\b(?:jamais\s+(?:de\s+|d'|du\s+|des\s+)?|(?:ne veu(?:t|lent) )?pas\s+(?:de\s+|d'|du\s+|des\s+)|aucune?\s+"
    r"|never\s+(?:any\s+)?|(?:does|do)\s+not\s+want\s+(?:any\s+)?|no\s+)(?P<x>.+)$"
)
_ONLY_AFTER = re.compile(r"^(?P<x>.+?)\s+(?:uniquement|exclusivement|only|exclusively)\b")
_ONLY_BEFORE = re.compile(r"\b(?:uniquement|exclusivement|only|exclusively)\s+(?P<x>.+)$")


def card_rules(preferences: str, notes: list[str] | tuple[str, ...] = ()) -> list[CardRule]:
    """The exclusions written on a card, clause by clause (split on . ; : ,).
    « jamais de verte » → ("interdit", "vert", {"vert"}) ; « Pommes 20 % uniquement » → ("seulement", "pomm", {"pomm", "20%"})."""
    found: list[CardRule] = []
    for text in [preferences, *notes]:
        for clause in re.split(r"[.;:,]", _norm(text or "")):
            clause = clause.strip()
            if not clause or "substitu" in clause:
                continue
            if m := _FORBID.search(clause):
                kind = "interdit"
            elif m := (_ONLY_AFTER.search(clause) or _ONLY_BEFORE.search(clause)):
                kind = "seulement"
            else:
                continue
            words = _name_words(m.group("x"), percent=True)
            head = _head(m.group("x"), english=_is_english(clause))
            if words and head:
                found.append((kind, head, frozenset(words)))
    return found


def allowed_by_card(missing_name: str, candidate_name: str, rules: list[CardRule]) -> bool:
    """False when the card forbids this candidate:
      « jamais de X »    the candidate's name holds every word of X
      « X uniquement »   only when the missing product holds X's product word (the family): the candidate
                         must hold every word X shares with the missing product (family word and percentage)."""
    cand = set(_name_words(candidate_name, percent=True))
    missing = set(_name_words(missing_name, percent=True))
    for kind, head, words in rules:
        if kind == "interdit" and words <= cand:
            return False
        if kind == "seulement" and head in missing and not (words & missing) <= cand:
            return False
    return True


def has_same_use_substitute(
    product_id: str,
    product_name: str,
    alternatives: list[dict],
    *,
    substitutes: dict[str, list[str]] | None = None,
    preferences: str = "",
    notes: list[str] | tuple[str, ...] = (),
) -> bool:
    """Is any alternative in stock a believable substitute (named by the docs, or sharing a distinctive word) that the
    client's card does not forbid? False → product_insight says so and the agent asks the caller instead of proposing
    lemons for strawberries, or a product the client's card rules out.
    No name → we can't tell: True (keep the previous behaviour)."""
    if not product_name:
        return True
    named = (doc_substitutes() if substitutes is None else substitutes).get(product_id, [])
    rules = card_rules(preferences, notes)
    # no `others` here: the family word (shared by the whole list) is exactly what says « same use »
    return any(
        (a.get("id") in named or name_match(product_name, a.get("name") or "") > 0)
        and allowed_by_card(product_name, a.get("name") or "", rules)
        for a in alternatives
        if (a.get("available") or 0) > 0
    )


def rank_alternatives(
    alternatives: list[dict],
    preferences: str,  # the card: what it forbids or imposes is dropped (card_rules); refusing is substitution_policy's job
    *,
    notes: list[str] | tuple[str, ...] = (),  # CRM notes of the card: read like the preferences
    for_product_id: str | None = None,  # the missing product: to find its substitute in the docs
    for_category: str | None = None,  # its category: "same use"
    for_product_name: str | None = None,  # its name: names sharing distinctive words first (name_match)
    for_unit: str | None = None,  # its unit: same unit breaks a tie
    substitutes: dict[str, list[str]] | None = None,  # default: read from the docs (doc_substitutes)
) -> list[dict]:
    """
    Order substitutes from best to worst (the agent proposes the first, with consent). Drops only what the client's
    card forbids or excludes (« jamais de … », « … uniquement »: card_rules); never changes one:
      1. in stock (available > 0)        2. named as substitute in the company docs
      3. same category (same use)        4. name sharing distinctive words with the missing product
      5. same unit                       6. active promo            7. then the ERP's own order
    Each dict: {id, name, unit, price, available, clientPrice?, promo?, category?} (product_insight / find_alternatives).
    """
    if substitutes is None:
        substitutes = doc_substitutes() if for_product_id else {}
    named = substitutes.get(for_product_id or "", [])
    rules = card_rules(preferences, notes)
    if rules:
        alternatives = [a for a in alternatives if allowed_by_card(for_product_name or "", a.get("name") or "", rules)]
    names = [a.get("name") or "" for a in alternatives]

    def key(item: tuple[int, dict]) -> tuple:
        position, alt = item
        doc_rank = named.index(alt.get("id")) if alt.get("id") in named else len(named)
        return (
            not (alt.get("available") or 0) > 0,
            doc_rank,
            not (for_category and alt.get("category") == for_category),
            -name_match(for_product_name or "", alt.get("name") or "", names),
            not (for_unit and alt.get("unit") == for_unit),
            not alt.get("promo"),
            position,
        )

    return [alt for _, alt in sorted(enumerate(alternatives), key=key)]
