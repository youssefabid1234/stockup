"""
Mock LLM — deterministic, no key, no network. Lets the whole stack demo offline.

It understands a handful of French intents and drives real tool calls against the ERP:
  "Bonjour, c'est la Poissonnerie Lemoine"   → search          → the client is now "the caller"
  "il reste du bar ?"                        → search(product) → get_product_stock
  "infos sur le Bistrot du Port"             → search(client)  → get_client
  "une commande pour le Bistrot…"            → search(client)  → create_draft_order
  "je voudrais 4 kg de bar de ligne"         → search(product) → create_draft_order with the line for the caller
                                               (or add_order_line when an order is already open in the conversation)
  "confirme la commande"                     → confirm_order (last order id seen in the conversation)
  anything else                              → search(everything)
Command mode (system prompt says "MODE COMMANDE", single stateless turn), see decide_command():
  "crée une pré-commande pour Lemoine, 4 kilos de bar pour jeudi" → search(client) → search(product) → create_draft_order
  "montre-moi le stock de turbot"                                → search(product) → get_product_stock

Greetings and fillers are stripped before searching. Each step looks at what already happened since the
last user message (and, for "who is calling" / "which order", at the whole conversation): a tiny state machine.
It is NOT an example of how to build an agent — it only exists so the kit runs without an API key.

Regexes use re.ASCII so that \\b behaves like in JavaScript (accented letters are not "word" characters):
the replies stay identical to the TypeScript version of this mock.
"""

import asyncio
import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from app.schemas import ChatMessage, ToolCall

from .base import LLMClient, LLMEvent, LLMRequest, LLMText, LLMToolCall, LLMUsage
from .http import new_call_id

A = re.ASCII
AI = re.ASCII | re.IGNORECASE

STOPWORDS = set(
    """bonjour bonsoir salut allo allô hello merci svp stp oui non euh ben bon alors voilà voila est-ce que qu quoi quel quelle quels quelles
   il elle ils on vous nous je j tu me m moi c ce s n est suis ici part
   le la les l un une des du de d au aux a à et ou pour avec sur dans en y cet cette ces mon ma mes votre vos son sa ses
   reste restent encore avez as ai a-t-il dispo disponible disponibles stock stocks combien
   info infos information informations fiche client clients donne donnez montre montrez dis dites
   commande commander commandes crée créer cree creer faire fais passe passer nouvelle nouveau prends prendre voudrais voudrait veux
   aimerais faut faudrait mets mettez mettre ajoute ajoutez ajouter rajoute rajoutez
   confirme confirmer valide valider kg kilo kilos s'il plaît plait c'est chez demain aujourd hui matin soir""".split()
)

GREETING = re.compile(r"^\s*(bonjour|bonsoir|salut|all[oô]|hello)\b", AI)
# "c'est la Poissonnerie Lemoine", "ici le Bistrot du Port", "de la part de …", "je suis …"
IDENTIFY = re.compile(r"\b(c['’]est|ici|de la part|je suis|je t[eé]l[eé]phone)\b", AI)

NUMBER_WORDS = {"deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "douze": 12, "quinze": 15, "vingt": 20}  # fmt: skip
NUMBER = rf"\d+(?:[.,]\d+)?|{'|'.join(NUMBER_WORDS)}"
UNITS = "kg|kilos?|kilogrammes?|pi[eè]ces?|pces?|douzaines?|colis|caisses?|cagettes?|bottes?|litres?|barquettes?"
# "4 kg de bar de ligne pour demain" → qty "4", product "bar de ligne pour demain"
QTY_LINE = re.compile(rf"\b({NUMBER})\s*(?:{UNITS})?\s+(?:de\s+|d['’]\s*)?(.+)", AI)
# The product phrase stops at "pour demain", "livré …", punctuation…
PRODUCT_END = re.compile(r"\s(?:pour|livr|à livrer|svp|s'il)\b|[,.;!?]", A)

ORDER_VERB = re.compile(r"\b(voudrais|voudrait|veux|faut|faudrait|aimerais|mets|mettez|mettre|ajoute|ajoutez|rajoute|prends|prendre|command|il me|donnez|envoyez)", A)  # fmt: skip
WITH_UNIT = re.compile(rf"\b({NUMBER})\s*({UNITS})\b", AI)

UNIT_FR = {"kg": "kg", "piece": "pièce(s)", "box": "colis", "dozen": "douzaine(s)", "liter": "L"}
WEEKDAYS = ["dimanche", "lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi"]  # JavaScript order: Sunday = 0
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]  # fmt: skip


# ── French formatting, as said on the phone ──


def fr_num(n: Any) -> str:
    """44.52 → "44,52", 1234.5 → "1 234,5" (at most 2 decimals)."""
    if isinstance(n, bool) or not isinstance(n, int | float):
        return str(n)
    d = Decimal(repr(n)).quantize(Decimal("0.01"), ROUND_HALF_EVEN)
    integer, _, decimals = f"{abs(d):f}".partition(".")
    decimals = decimals.rstrip("0")
    grouped = f"{int(integer):,}".replace(",", " ")  # French thousands separator: narrow no-break space
    return ("-" if d < 0 else "") + grouped + (f",{decimals}" if decimals else "")


def fr_day(iso: Any) -> str:
    """"2026-11-25" → "le mercredi 25 novembre"."""
    if not isinstance(iso, str) or not re.match(r"^\d{4}-\d{2}-\d{2}", iso, A):
        return f"le {iso}"
    d = date.fromisoformat(iso[:10])
    return f"le {WEEKDAYS[(d.weekday() + 1) % 7]} {d.day} {MONTHS[d.month - 1]}"


# ── Understanding the user's sentence ──


@dataclass
class Line:
    qty: int | float
    product: str


def parse_line(text: str) -> Line | None:
    """"je voudrais 4 kg de bar de ligne pour demain" → Line(qty=4, product="bar ligne")."""
    m = QTY_LINE.search(text.lower())
    if not m:
        return None
    qty = NUMBER_WORDS.get(m[1]) or float(m[1].replace(",", "."))
    qty = int(qty) if float(qty).is_integer() else qty
    product = extract_query(PRODUCT_END.split(m[2])[0])
    return Line(qty, product) if qty > 0 and product else None


def detect_intent(text: str) -> str:
    """greeting | stock | client | order | line | confirm | search"""
    t = text.lower()
    if re.search(r"\b(confirm|valid)", t, A):
        return "confirm"
    if re.search(r"\b(reste|stock|dispo|combien)", t, A):
        return "stock"
    # A quantity + product, said with an order verb ("je voudrais 4 kg de …") or with a unit ("et deux douzaines d'huîtres").
    if parse_line(t) and (ORDER_VERB.search(t) or WITH_UNIT.search(t)):
        return "line"
    if "command" in t:
        return "order"
    if re.search(r"\b(client|fiche|infos?|habitude)", t, A):
        return "client"
    if re.search(r"^(bonjour|salut|allo|allô|hello)[\s,!.]*$", t.strip(), A):
        return "greeting"
    return "search"


def extract_query(text: str) -> str:
    """Keep the meaningful words: "il vous reste du bar ?" → "bar"."""
    t = re.sub(r"[’']", " ", text.lower())
    t = "".join(c if c.isalpha() or c.isnumeric() or c.isspace() or c == "-" else " " for c in t)
    return " ".join(w for w in t.split() if w not in STOPWORDS and not re.fullmatch(r"[0-9]+", w))


# ── Reading the conversation ──


@dataclass
class ToolResult:
    name: str | None
    data: Any


def parse(content: str) -> Any:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return content


def last_user_index(messages: list[ChatMessage]) -> int:
    return max((i for i, m in enumerate(messages) if m.role == "user"), default=-1)


def results_after(messages: list[ChatMessage], index: int) -> list[ToolResult]:
    return [ToolResult(m.name, parse(m.content)) for m in messages[index + 1 :] if m.role == "tool"]


def error_of(result: ToolResult | None) -> str | None:
    return result.data.get("error") if result and isinstance(result.data, dict) else None


def first(data: Any) -> dict | None:
    return data[0] if isinstance(data, list) and data else None


def find_caller(messages: list[ChatMessage]) -> dict | None:
    """The client identified earlier in the conversation: last get_client, or last search whose top hit was a client."""
    for m in reversed(messages):
        if m.role != "tool":
            continue
        d = parse(m.content)
        if m.name == "get_client" and isinstance(d, dict) and isinstance(d.get("id"), str):
            return {"id": d["id"]}
        if m.name == "search" and (top := first(d)) and top.get("type") == "client":
            return {"id": top["id"]}
    return None


def find_last_order(messages: list[ChatMessage], editable_only: bool = False) -> dict | None:
    """Last order seen in the conversation (optionally only if still editable: draft / confirmed)."""
    for m in reversed(messages):
        if m.role != "tool":
            continue
        d = parse(m.content)
        if isinstance(d, dict) and isinstance(d.get("id"), str) and d["id"].startswith("ord_"):
            if editable_only and d.get("status") and d["status"] not in ("draft", "confirmed"):
                return None
            return {"id": d["id"], "status": d.get("status")}
    return None


def warnings(order: Any) -> str:
    w = [x.get("message") for x in (order.get("warnings") or [])] if isinstance(order, dict) else []
    return f" Attention : {' ; '.join(map(str, w))}." if w else ""


def describe_line(line: dict | None, fallback: str) -> str:
    """{qty: 4, unit: "kg", productName: "Bar"} → "4 kg de Bar"."""
    if not line:
        return fallback
    return f"{fr_num(line.get('qty'))} {UNIT_FR.get(line.get('unit'), line.get('unit'))} de {line.get('productName')}"


def call(name: str, args: dict) -> ToolCall:
    return ToolCall(id=new_call_id("mock"), name=name, arguments=args)


# ── Conversation mode (chat / voice) ──


def decide(messages: list[ChatMessage]) -> ToolCall | str:
    """The next step: either a tool call or the final French answer."""
    last_user = last_user_index(messages)
    user_text = messages[last_user].content if last_user >= 0 else ""
    before = messages[:last_user]  # the conversation so far (who is calling, which order is open)
    results = results_after(messages, last_user)  # what happened since the user spoke
    last = results[-1] if results else None
    intent = detect_intent(user_text)
    query = extract_query(user_text)

    if error := error_of(last):
        return f"Désolé, je n'arrive pas à obtenir l'information : {error}"

    if intent == "greeting":
        return "Bonjour ! Je vous écoute : un client, un produit, une commande ?"

    if intent == "confirm":
        if not last:
            order = find_last_order(messages)
            return call("confirm_order", {"orderId": order["id"]}) if order else "Je ne vois pas de commande en cours à confirmer."
        return f"C'est confirmé : commande {last.data.get('number')}.{warnings(last.data)}"

    if intent == "line":
        line = parse_line(user_text)
        order = find_last_order(before, editable_only=True)
        client = find_caller(before)
        if not last:
            if not order and not client:
                return "Pour quel client est-ce ? Dites-moi le nom de l'établissement."
            return call("search", {"query": line.product, "types": ["product"]})
        if last.name == "search":
            top = first(last.data)
            if not top:
                return f"Je n'ai pas trouvé de produit pour « {line.product} »."
            new_line = {"productId": top["id"], "qty": line.qty}
            if order:
                return call("add_order_line", {"orderId": order["id"], **new_line})
            return call("create_draft_order", {"clientId": client["id"], "lines": [new_line]})
        if last.name in ("create_draft_order", "add_order_line"):
            d = last.data
            added = (d.get("lines") or [None])[-1]
            # Only the alerts about the line just added (the others were already said).
            own = [w for w in d.get("warnings") or [] if not added or w.get("productId") == added.get("productId")]
            return (
                f"C'est noté : {describe_line(added, 'la ligne')} sur la commande {d.get('number')} (brouillon) "
                f"pour {d.get('client')}, livraison {fr_day(d.get('deliveryDate'))}.{warnings({'warnings': own})} Autre chose ?"
            )

    if not last:
        if not query:
            if GREETING.search(user_text):
                return "Bonjour ! Je vous écoute : un client, un produit, une commande ?"
            return "Pouvez-vous préciser le client ou le produit ?"
        types = ["product"] if intent == "stock" else ["client"] if intent in ("client", "order") else None
        return call("search", {"query": query, **({"types": types} if types else {})})

    if last.name == "search":
        hits = last.data if isinstance(last.data, list) else []
        if not hits:
            return f"Je n'ai rien trouvé pour « {query} »."
        top = hits[0]
        if intent == "stock" and top["type"] == "product":
            return call("get_product_stock", {"productId": top["id"]})
        if intent == "client" and top["type"] == "client":
            return call("get_client", {"clientId": top["id"]})
        if intent == "order" and top["type"] == "client":
            return call("create_draft_order", {"clientId": top["id"]})
        if top["type"] == "client" and (GREETING.search(user_text) or IDENTIFY.search(user_text)):
            hello = "Bonjour" if GREETING.search(user_text) else "Très bien"
            return f"{hello}, {top['label']} ! Je vous écoute, que puis-je faire pour vous ?"
        return f"J'ai trouvé : {', '.join(h['label'] for h in hits[:3])}."

    d = last.data if isinstance(last.data, dict) else {}
    match last.name:
        case "get_product_stock":
            expiry = f", prochaine DLC {fr_day(d['nextExpiry'])}" if d.get("nextExpiry") else ""
            return f"{d.get('name')} : {fr_num(d.get('available'))} {UNIT_FR.get(d.get('unit'), d.get('unit'))} disponibles{expiry}."
        case "get_client":
            usual = [u.get("productName") for u in (d.get("usual") or [])[:3]]
            habits = f" D'habitude : {', '.join(usual)}." if usual else ""
            return f"{d.get('name')}, à {d.get('city')}.{habits}"
        case "create_draft_order":
            return (
                f"C'est noté : commande {d.get('number')} créée en brouillon pour {d.get('client')}, "
                f"livraison {fr_day(d.get('deliveryDate'))}. Que voulez-vous ajouter ?"
            )
        case _:
            return "C'est fait."


# ── Command mode (single turn, act-first) ──

NOT_A_CLIENT = re.compile(rf"^({'|'.join(WEEKDAYS)}|demain|aujourd|ce |cette |la semaine|le \d)", AI)
FOR_WHOM = re.compile(r"\bpour\s+(.+?)(?=\s*[,;.]|\s+\d|\s+pour\b|\s+livr|$)", AI)


def command_client(text: str) -> str | None:
    """"… pour Lemoine, 4 kilos …" / "4 kg de bar pour le Bistrot du Port pour jeudi" → "lemoine" / "bistrot port"."""
    for m in FOR_WHOM.finditer(text):
        who = m[1].strip()
        if who and not NOT_A_CLIENT.search(who) and not re.search(r"\d", who, A):
            return extract_query(who) or None
    return None


def command_date(text: str, system: str) -> str | None:
    """"jeudi" / "demain" → YYYY-MM-DD, relative to the ERP's "today" written in the system prompt."""
    today = re.search(r"\((\d{4}-\d{2}-\d{2})\)", system)
    if not today:
        return None
    d = date.fromisoformat(today[1])
    t = text.lower()
    if re.search(r"\bdemain\b", t, A):
        return (d + timedelta(days=1)).isoformat()
    wd = next((i for i, w in enumerate(WEEKDAYS) if re.search(rf"\b{w}\b", t, A)), -1)
    if wd < 0:
        return None
    days_ahead = (wd - (d.weekday() + 1) % 7 + 7) % 7 or 7  # the next one, never today
    return (d + timedelta(days=days_ahead)).isoformat()


def decide_command(messages: list[ChatMessage], system: str, tool_names: list[str]) -> ToolCall | str:
    last_user = last_user_index(messages)
    user_text = messages[last_user].content if last_user >= 0 else ""
    results = results_after(messages, last_user)
    last = results[-1] if results else None
    if error := error_of(last):
        return f"Échec : {error}"

    line = parse_line(user_text)
    client = command_client(user_text)
    if line and client:
        searches = [r for r in results if r.name == "search"]
        if not last:
            return call("search", {"query": client, "types": ["client"]})
        if last.name == "search" and len(searches) == 1:
            if not first(searches[0].data):
                return f"Je ne trouve pas le client « {client} »."
            return call("search", {"query": line.product, "types": ["product"]})
        if last.name == "search":
            c, p = first(searches[0].data), first(searches[1].data)
            if not p:
                return f"Je ne trouve pas le produit « {line.product} »."
            delivery_date = command_date(user_text, system)
            return call(
                "create_draft_order",
                {
                    "clientId": c["id"],
                    "lines": [{"productId": p["id"], "qty": line.qty}],
                    **({"deliveryDate": delivery_date} if delivery_date else {}),
                },
            )
        if last.name == "create_draft_order":
            d = last.data
            what = describe_line((d.get("lines") or [None])[0], "la commande")
            return f"Pré-commande {d.get('number')} créée pour {d.get('client')} : {what}, livraison {fr_day(d.get('deliveryDate'))}.{warnings(d)}"

    if re.search("factur", user_text, re.I) and re.search("pay|régl|regl", user_text, re.I):
        if any(re.search("pay|paid|paiement", n, re.I) for n in tool_names):
            return "Le mode démo (mock) ne sait pas encore enregistrer un paiement : branchez un vrai LLM."
        return "Je ne peux pas encore marquer une facture comme payée : aucun outil de paiement n'est branché."

    # Everything else: the conversational state machine, on a cleaned-up sentence, with command-style endings.
    cleaned = re.sub(r"\b(montre|montrez|affiche|affichez|ouvre|ouvrez|donne|donnez)(-moi|-nous)?\b", " ", user_text, flags=AI)
    cleaned = re.sub(r"pr[ée]-?commande", "commande", cleaned, flags=re.I)
    following = decide([*messages[:last_user], ChatMessage(role="user", content=cleaned), *messages[last_user + 1 :]])
    if isinstance(following, str):
        return re.sub(r"\s*(Autre chose|Que voulez-vous ajouter|Je vous écoute[^?]*)\s*\?$", "", following).strip()
    return following


class MockLLM(LLMClient):
    provider = "mock"
    model = "mock-fr-intents"

    async def stream(self, req: LLMRequest) -> AsyncIterator[LLMEvent]:
        if "MODE COMMANDE" in req.system:
            step = decide_command(req.messages, req.system, [t.name for t in req.tools])
        else:
            step = decide(req.messages)
        if isinstance(step, ToolCall):
            yield LLMToolCall(step)
        else:
            for word in filter(None, re.split(r"(?<= )", step)):
                await asyncio.sleep(0.008)  # feels like streaming
                yield LLMText(word)
        yield LLMUsage(0, 0)
