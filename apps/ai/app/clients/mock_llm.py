"""
Mock LLM — deterministic, no key, no network. Lets the whole stack demo offline.

It understands a handful of English intents and drives real tool calls against the ERP:
  "Hello, it's the Poissonnerie Lemoine" → search → the client is now "the caller"
  "il reste du bar ?"                        → search(product) → get_product_stock
  "infos about the Bistrot du Port" → search(client) → get_client
  "a command for the Bistrot..." → search(client) → create_draft_order
  "I would like 4 kg of line bar" → search(product) → create_draft_order with the line for the caller
                                               (or add_order_line when an order is already open in the conversation)
  "confirms the order" → confirm_order (last order id seen in the conversation)
  anything else                              → search(everything)
Command mode (system prompt says "Single-turn voice command", single stateless turn), see decide_command():
  "creates a pre-order for Lemoine, 4 kilos of bar for Thursday" → search(client) → search(product) → create_draft_order
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

STOPWORDS = set("""hi hello good morning afternoon thanks please yes no would could can do does did
    you your we our me my i d like need want order create draft open for the a an any some of in
    have has stock available availability left how much many is are show tell about customer client
    record file details tomorrow today delivery on to here from this it's it s and add put down
    kg kilos kilograms grams litres liters blocks bags boxes sacks units""".split())
GREETING = re.compile(r"^\s*(?:hi|hello|good (?:morning|afternoon|evening))\b", AI)
IDENTIFY = re.compile(r"\b(?:this is|calling from|I'm|I am|speaking)\b", AI)
NUMBER_WORDS = dict(zip("one two three four five six seven eight nine ten".split(), range(1, 11)))
NUMBER_WORDS.update(twelve=12, fifteen=15, twenty=20)
NUMBER = rf"\d+(?:[.,]\d+)?|{'|'.join(NUMBER_WORDS)}"
UNITS = r"kg|kilograms?|kilos?|grams?|pieces?|units?|dozens?|boxes|box|cartons?|sacks?|bags?|bunches|litres?|liters?|packs?|blocks?|slabs?"
QTY_LINE = re.compile(rf"\b({NUMBER})\s*(?:{UNITS})?\s+(?:of\s+)?(.+)", AI)
PRODUCT_END = re.compile(r"\s(?:for|deliver\w*|please|on)\b|[,.;!?]", AI)
ORDER_VERB = re.compile(r"\b(?:want|need|take|add|order|like|give|put|send)\b", AI)
WITH_UNIT = re.compile(rf"\b({NUMBER})\s*({UNITS})\b", AI)
UNIT_FR = {"kg": "kg", "piece": "pieces", "box": "boxes", "dozen": "dozen", "liter": "L"}
WEEKDAYS = "sunday monday tuesday wednesday thursday friday saturday".split()

def fr_num(n: Any) -> str:
    if isinstance(n, bool) or not isinstance(n, (float, int)):
        return str(n)
    rounded = Decimal(repr(n)).quantize(Decimal("0.01"), ROUND_HALF_EVEN)
    return f"{rounded:,.2f}".rstrip("0").rstrip(".")

def fr_day(iso: Any) -> str:
    if not isinstance(iso, str) or not re.match(r"^\d{4}-\d{2}-\d{2}", iso):
        return str(iso)
    day = date.fromisoformat(iso[:10])
    return f"{day:%A} {day.day} {day:%B}"


@dataclass
class Line:
    qty: int | float
    product: str


def parse_line(text: str) -> Line | None:
    """"I would like 4 kg of line bar for tomorrow" → Line(qty=4, product="bar line")."""
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
    if re.search(r"\b(stock|available|left|how much|how many|do you have)", t, A):
        return "stock"
    # A quantity + product, said with an order verb ("I would like 4 kg of ...") or with a unit ("and two dozen oysters").
    if parse_line(t) and (ORDER_VERB.search(t) or WITH_UNIT.search(t)):
        return "line"
    if "order" in t:
        return "order"
    if re.search(r"\b(client|customer|profile|usual|info)", t, A):
        return "client"
    if re.search(r"^(hi|hello|good morning|good afternoon)[\s,!.]*$", t.strip(), A):
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
    return f" Attention: {' ; '.join(map(str, w))}." if w else ""


def describe_line(line: dict | None, fallback: str) -> str:
    """{qty: 4, unit: "kg", productName: "Bar"} → "4 kg de Bar"."""
    if not line:
        return fallback
    return f"{fr_num(line.get('qty'))} {UNIT_FR.get(line.get('unit'), line.get('unit'))} of {line.get('productName')}"


def call(name: str, args: dict) -> ToolCall:
    return ToolCall(id=new_call_id("mock"), name=name, arguments=args)


# ── Conversation mode (chat / voice) ──


def decide(messages: list[ChatMessage]) -> ToolCall | str:
    """The next step: either a tool call or the final English answer."""
    last_user = last_user_index(messages)
    user_text = messages[last_user].content if last_user >= 0 else ""
    before = messages[:last_user]  # the conversation so far (who is calling, which order is open)
    results = results_after(messages, last_user)  # what happened since the user spoke
    last = results[-1] if results else None
    intent = detect_intent(user_text)
    query = extract_query(user_text)

    if error := error_of(last):
        return f"Sorry, I can't get the information: {error}"

    if intent == "greeting":
        return "Hello! How can I help you with a customer, a product or an order?"

    if intent == "confirm":
        if not last:
            order = find_last_order(messages)
            return call("confirm_order", {"orderId": order["id"]}) if order else "I don't see any orders in progress to confirm."
        return f"It's confirmed: order {last.data.get('number')}.{warnings(last.data)}"

    if intent == "line":
        line = parse_line(user_text)
        order = find_last_order(before, editable_only=True)
        client = find_caller(before)
        if not last:
            if not order and not client:
                return "Which business are you calling from?"
            return call("search", {"query": line.product, "types": ["product"]})
        if last.name == "search":
            top = first(last.data)
            if not top:
                return f"I did not find a product for “{line.product}”."
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
                f"Added {describe_line(added, 'the item')} to draft order {d.get('number')} "
                f"for {d.get('client')}, for delivery on {fr_day(d.get('deliveryDate'))}.{warnings({'warnings': own})} Anything else?"
            )

    if not last:
        if not query:
            if GREETING.search(user_text):
                return "Hello! How can I help you with a customer, a product or an order?"
            return "Can you specify the customer or product?"
        types = ["product"] if intent == "stock" else ["client"] if intent in ("client", "order") else None
        return call("search", {"query": query, **({"types": types} if types else {})})

    if last.name == "search":
        hits = last.data if isinstance(last.data, list) else []
        if not hits:
            return f"I didn't find anything for “{query}”."
        top = hits[0]
        if intent == "stock" and top["type"] == "product":
            return call("get_product_stock", {"productId": top["id"]})
        if intent == "client" and top["type"] == "client":
            return call("get_client", {"clientId": top["id"]})
        if intent == "order" and top["type"] == "client":
            return call("create_draft_order", {"clientId": top["id"]})
        if top["type"] == "client" and (GREETING.search(user_text) or IDENTIFY.search(user_text)):
            hello = "Hello" if GREETING.search(user_text) else "All right"
            return f"{hello}, {top['label']} How can I help?"
        return f"I found: {', '.join(h['label'] for h in hits[:3])}."

    d = last.data if isinstance(last.data, dict) else {}
    match last.name:
        case "get_product_stock":
            expiry = f", next expiry {fr_day(d['nextExpiry'])}" if d.get("nextExpiry") else ""
            return f"{d.get('name')} : {fr_num(d.get('available'))} {UNIT_FR.get(d.get('unit'), d.get('unit'))} available{expiry}."
        case "get_client":
            usual = [u.get("productName") for u in (d.get("usual") or [])[:3]]
            habits = f" Usually: {', '.join(usual)}." if usual else ""
            return f"{d.get('name')}, in {d.get('city')}.{habits}"
        case "create_draft_order":
            return (
                f"Draft order {d.get('number')} created for {d.get('client')}, "
                f"for delivery on {fr_day(d.get('deliveryDate'))}. What do you want to add?"
            )
        case _:
            return "It's done."


# ── Command mode (single turn, act-first) ──

NOT_A_CLIENT = re.compile(rf"^({'|'.join(WEEKDAYS)}|tomorrow|today|this |next |the \d)", AI)
FOR_WHOM = re.compile(r"\bfor\s+(.+?)(?=\s*[,;.]|\s+\d|\s+for\b|\s+deliver|$)", AI)


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
    if re.search(r"\btomorrow\b", t, A):
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
        return f"Failed: {error}"

    line = parse_line(user_text)
    client = command_client(user_text)
    if line and client:
        searches = [r for r in results if r.name == "search"]
        if not last:
            return call("search", {"query": client, "types": ["client"]})
        if last.name == "search" and len(searches) == 1:
            if not first(searches[0].data):
                return f"I can't find the client “{client}”."
            return call("search", {"query": line.product, "types": ["product"]})
        if last.name == "search":
            c, p = first(searches[0].data), first(searches[1].data)
            if not p:
                return f"I can't find the product “{line.product}”."
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
            what = describe_line((d.get("lines") or [None])[0], "the command")
            return f"Pre-order {d.get('number')} created for {d.get('client')} : {what}, delivery {fr_day(d.get('deliveryDate'))}.{warnings(d)}"

    if re.search("invoice", user_text, re.I) and re.search("pay", user_text, re.I):
        if any(re.search("pay|paid", n, re.I) for n in tool_names):
            return "Demo mode (mock) doesn't know how to save a payment yet: plug in a real one LLM."
        return "I can't mark an invoice as paid yet: no payment tool is connected."

    # Everything else: the conversational state machine, on a cleaned-up sentence, with command-style endings.
    cleaned = re.sub(r"\b(show|display|open|give)(?: me| us)?\b", " ", user_text, flags=AI)
    cleaned = re.sub(r"pre-?order", "order", cleaned, flags=re.I)
    following = decide([*messages[:last_user], ChatMessage(role="user", content=cleaned), *messages[last_user + 1 :]])
    if isinstance(following, str):
        return re.sub(r"\s*(Anything else|What do you want to add|How can I help[^?]*)\s*\?$", "", following).strip()
    return following


class MockLLM(LLMClient):
    provider = "mock"
    model = "mock-en-intents"

    async def stream(self, req: LLMRequest) -> AsyncIterator[LLMEvent]:
        if "Single-turn voice command" in req.system:
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
