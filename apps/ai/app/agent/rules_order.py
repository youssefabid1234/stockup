"""
OWNER: Amine Khalil · switch TEAM_ORDER_RULES · contract: docs/team/interfaces.md §4

« La commande juste » : what the agent must understand and check so that the order in the ERP is exactly what the
caller meant. Real life: Lucie knows "10 de tradi" = 10 sacks of 25 kg, "comme d'hab" = the usual basket, never
confirms without reading the order back, never promises anything to a blocked client.

Two parts:
  1. ORDER_RULES: text added to the system prompt (voice + chat modes) when the switch is on.
  2. Deterministic helpers (quantities, units, dates): the brief says "du code déterministe pour ce qui n'a pas
     Faster and never wrong. Business rules that touch prices / stock / credit stay in the
     backend (AGENTS.md): read the ERP's order warnings (client_blocked, no_route…) instead of re-coding them.
     The dates are exposed to the model by the tool check_delivery_date (tools/delivery.py).

Decision (T0, see docs/team/status/amine-khalil.md): the ERP's delivery days are the truth. Some CRM notes say
"Closed on Wednesday" for clients the ERP delivers on Wednesdays — and the order history shows they ARE delivered on
Wednesdays after the note. So the agent never claims a client is closed; only the caller can say so.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta

from app import team_flags

ORDER_RULES = """Phone order rules:
- Use tools silently, then speak once. Use the caller's everyday names for products.
- Flour and sugar are sold by the sack (25 kg, or 10 kg for einkorn). Ten traditional flour means ten sacks. Butter, chocolate and nuts are sold by weight, milk and cream by litre, frozen pastries and packaging by box, yeast by 500 g block, eggs by tray of 30.
- Chocolatine and pain au chocolat refer to the same pastry. Respect the caller's terms.
- When quantities and products are clear, call place_order once with the caller's product words in said, quantity, spoken units and day. It checks the day, resolves products, converts units, creates or edits the draft and prepares a readback. If it returns next, ask that question before proceeding.
- Keep one draft per call. Pass its order_id when changing a quantity, removing a line (quantity zero) or changing the date. Use cancel_draft_order if the caller abandons the order.
- “The usual” means the usual basket in the customer record. Mention two or three main items and ask whether to keep the rest as usual.
- Use ERP delivery days. Ignore outdated “Closed on …” notes. If the caller announces a closure, offer the next delivery day and save the new information with save_context.
- Read back the products, quantities, date, relevant alerts and delivery charge from the tool. Confirm unusually large quantities in askFirst. Check duplicateDrafts and sameDayOrders. Cancel identical duplicate drafts. Ask about other open drafts or existing orders for the same day before combining or cancelling them.
- For prices use quote_line and read its say and total. Never calculate pack prices or totals mentally.
- After readback, call confirm_order with the caller's exact answer in client_answer. Follow the returned next step for an ambiguous answer or change. Never confirm a blocked order. For a blocked account, record the customer's message and arrange the appropriate handoff without disclosing internal credit notes."""


def order_rules_section() -> str:
    """What prompts.py adds to the system prompt. '' when the switch is off or the rules are empty."""
    return ORDER_RULES.strip() if team_flags.order_rules() else ""


# ── Deterministic helpers: pure functions, unit-tested in tests/test_rules_order.py ──

WEEKDAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAYS_FR = {"lundi": "mon", "mardi": "tue", "mercredi": "wed", "jeudi": "thu", "vendredi": "fri", "samedi": "sat", "dimanche": "sun"}  # fmt: skip
DAY_LABEL = dict(zip(WEEKDAYS, ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"), strict=True))
DAYS_FR.update({name.lower(): code for code, name in DAY_LABEL.items()})
ASAP = ("asap", "as soon as possible", "earliest", "next delivery", "au plus vite", "des que possible")
CUTOFF_HOUR = 17  # order before 17h for next-morning delivery (02-journee-type.md)
CUTOFF_HOUR_LAURAGAIS = 12  # Lauragais-Tarn route: order the day before, before noon
LAURAGAIS_ZONE = "Lauragais & Tarn"


def _norm(s: str) -> str:
    """ lower case, no accents, single spaces: "After tomorrow" → "after tomorrow"."""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", s.lower()).strip()


def can_deliver(today: date, delivery_days: list[str], d: date, now_hour: float = 6, cutoff_hour: float = CUTOFF_HOUR) -> bool:
    """True when `d` is a delivery day of the client, after today, and the order is still in time for it."""
    if d <= today or WEEKDAYS[d.weekday()] not in delivery_days:
        return False
    return d - timedelta(days=1) > today or now_hour < cutoff_hour


def first_possible(today: date, delivery_days: list[str], now_hour: float = 6, cutoff_hour: float = CUTOFF_HOUR) -> date | None:
    """The first date the client can be delivered (None if the client has no delivery day)."""
    return next(
        (today + timedelta(days=i) for i in range(1, 15) if can_deliver(today, delivery_days, today + timedelta(days=i), now_hour, cutoff_hour)),
        None,
    )


def parse_asked_day(today: date, asked: str | None) -> date | None | str:
    """What the caller said → a date, "asap", or None when it is not understood / not a future day.
    Examples include tomorrow, next Thursday, 26/11, the 26th and ASAP."""
    if asked is None or not asked.strip():
        return "asap"
    a = _norm(asked)
    if any(k in a for k in ASAP):
        return "asap"
    if any(term in a for term in ("day after tomorrow", "apres-demain", "apres demain")):
        return today + timedelta(days=2)
    if "tomorrow" in a or "demain" in a:
        return today + timedelta(days=1)
    if "today" in a or "aujourd" in a or "this morning" in a or "this noon" in a:
        return today
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", a):
        return date(int(m[1]), int(m[2]), int(m[3]))
    if m := re.search(r"\b(\d{1,2})\s*/\s*(\d{1,2})(?:st|nd|rd|th)?\b", a):
        return _future(today, int(m[1]), int(m[2]))
    for name, code in DAYS_FR.items():
        if re.search(rf"\b{name}\b", a):
            ahead = (WEEKDAYS.index(code) - today.weekday()) % 7 or 7  # "mardi" said on a Tuesday = next Tuesday
            return today + timedelta(days=ahead)
    if m := re.search(r"\b(?:le\s+)?(\d{1,2})(?:st|nd|rd|th)?\b", a):
        return _future(today, int(m[1]), today.month)
    return None


def _future(today: date, day: int, month: int) -> date | None:
    """Day/month without a year: the next occurrence from today."""
    for year in (today.year, today.year + 1):
        try:
            d = date(year, month, day)
        except ValueError:
            return None
        if d >= today:
            return d
    return None


def next_delivery_date(
    today: date, delivery_days: list[str], asked: str | None = None, now_hour: float = 6, cutoff_hour: float = CUTOFF_HOUR
) -> date | None:
    """
    The delivery date for "jeudi", "demain", "au plus vite"… given the client's delivery days and the order cut-off
    (17h for the next morning; 12h the day before for the Lauragais-Tarn route).
    Use the ERP's business date (GET /api/meta → today), never the real clock.
    Returns None if the asked day is not delivered for this client, already gone, or too late to order for.
    """
    wanted = parse_asked_day(today, asked)
    if wanted == "asap":
        return first_possible(today, delivery_days, now_hour, cutoff_hour)
    if not isinstance(wanted, date):
        return None
    return wanted if can_deliver(today, delivery_days, wanted, now_hour, cutoff_hour) else None


def french_day(d: date) -> str:
    """date(2026, 11, 26) → "Thursday, November 26"."""
    return f"{DAY_LABEL[WEEKDAYS[d.weekday()]]} {d.day} {d:%B}"


def delivery_answer(
    today: date, delivery_days: list[str], asked: str | None, now_hour: float = 6, zone: str | None = None
) -> dict:
    """Everything the agent needs to answer about a delivery day, as small JSON (used by check_delivery_date)."""
    cutoff = CUTOFF_HOUR_LAURAGAIS if zone == LAURAGAIS_ZONE else CUTOFF_HOUR
    days_fr = [DAY_LABEL[d] for d in WEEKDAYS if d in delivery_days]
    nxt = first_possible(today, delivery_days, now_hour, cutoff)
    wanted = parse_asked_day(today, asked)
    out: dict = {"deliveryDays": days_fr}
    if wanted == "asap" or (date_ok := next_delivery_date(today, delivery_days, asked, now_hour, cutoff)) is not None:
        d = nxt if wanted == "asap" else date_ok
        if d is None:
            return {**out, "ok": False, "reason": "No delivery days are on file for this customer."}
        return {**out, "ok": True, "date": d.isoformat(), "say": french_day(d)}
    if not isinstance(wanted, date):
        reason = f"Unrecognised delivery day: {asked}"
    elif wanted <= today:
        reason = "Today's delivery routes have left. Pickup at the depot may be possible."
    elif WEEKDAYS[wanted.weekday()] not in delivery_days:
        reason = f"No delivery on {DAY_LABEL[WEEKDAYS[wanted.weekday()]]} (delivery days: {', '.join(days_fr)})"
    else:
        limit = "before noon the previous day" if cutoff == CUTOFF_HOUR_LAURAGAIS else "before 5 pm the previous day"
        reason = f"This delivery is past the cutoff. Order {limit}"
    return {
        **out,
        "ok": False,
        "asked": french_day(wanted) if isinstance(wanted, date) else asked,
        "reason": reason,
        **({"nextPossible": nxt.isoformat(), "sayNext": french_day(nxt)} if nxt else {}),
    }


UNIT_ALIASES = {
    "kg": ("kg", "kilo", "kilos", "kilogram", "kilograms", "kilogramme", "kilogrammes"),
    "l": ("l", "liter", "liters", "litre", "litres"),
    "g": ("g", "gram", "grams", "gramme", "grammes"),
}


def _said(unit: str | None) -> str | None:
    if not unit:
        return None
    u = _norm(unit).rstrip(".")
    return next((k for k, aliases in UNIT_ALIASES.items() if u in aliases), u)


def sacks_from_words(product_unit: str, qty: float, said_unit: str | None) -> float:
    """
    Convert what was said into the product's selling unit, e.g. "10 de tradi" → 10 sacks, "50 kilos de tradi" → 2.
    `product_unit` is the package the product is sold by ("sac 25 kg", "plaque 2 kg", "carton 140"…); a product sold
    by weight or volume passes "kg" / "l" and the quantity stays as said.
    No unit said ("10 de tradi") = packages. A weight said for a weighed package = weight / package weight
    (may be fractional: the agent then asks, e.g. 40 kg of 25 kg sacks).
    """
    said = _said(said_unit)
    pu = _norm(product_unit)
    if pu in ("kg", "l", "litre", "kilo"):
        return qty
    if said is None or said in ("sac", "sacs", "carton", "cartons", "plaque", "plaques", "piece", "pieces"):
        return qty
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|l|g)\b", pu)
    if not m:
        return qty
    size, size_unit = float(m[1].replace(",", ".")), m[2]
    if said == "g" and size_unit == "kg":
        qty, said = qty / 1000, "kg"
    if said != size_unit:
        return qty
    return round(qty / size, 3)


# ── T3 / T4: read the order back, the ERP's warnings, franco, unusual quantities (used by tools/order_review.py) ──

FRANCO_HT = 150.0  # « Franco de port 150 € HT ; en dessous, 12 € de livraison » (01-entreprise.md)
DELIVERY_FEE_HT = 12.0
UNUSUAL_RATIO = 5  # a line at 5× (or more) the client's usual quantity is read back and confirmed first

# What the caller may hear for each ERP warning code. None = internal, never said to the caller.
# `blocks` = the order must not be confirmed while it is there.
WARNINGS_FOR_CALLER: dict[str, tuple[str | None, bool]] = {
    "client_blocked": ("Your account is blocked. Our accounts team will call you back before we can confirm an order.", True),
    "credit_limit": ("This order exceeds your credit limit and needs approval from our accounts team.", True),
    "no_route": ("We don't deliver to your address that day.", True),
    "insufficient_stock": (None, True),  # said per product below, with what is left
    "expiring_soon": (None, False),  # a FEFO lot close to its date: the warehouse's business
    "price_below_cost": (None, False),  # margin: internal
}


def fr_number(x: float) -> str:
    """12.0 → "12", 1.5 → "1,5"."""
    return f"{x:g}"


def _plural(word: str, n: float) -> str:
    if word == "loaf" and n != 1:
        return "loaves"
    if word == "box" and n != 1:
        return "boxes"
    if n == 1 or word.endswith("s"):
        return word
    return word + ('es' if word.endswith(('ch', 'sh')) else 's')


def say_quantity(qty: float, unit: str | None, caliber: str | None = None) -> str:
    """How a quantity is said: (12, piece, "sac 25 kg") → "12 sacs", (40, kg) → "40 kilos", (4, box, "carton 140") → "4 cartons"."""
    if unit == "kg":
        return f"{fr_number(qty)} {'kilo' if qty <= 1 else 'kilos'}"
    if unit in ("liter", "l"):
        return f"{fr_number(qty)} {'litre' if qty <= 1 else 'litres'}"
    word = package_word(caliber, "carton" if unit == "box" else "piece")
    return f"{fr_number(qty)} {_plural(word, qty)}"

def package_word(caliber: str | None, fallback: str) -> str:
    words = re.findall(r"[a-zA-Z]+", (caliber or "").lower())
    return next((w for w in words if w not in {"kg", "g", "l", "of", "x"}), fallback)


def short_name(product_name: str) -> str:
    """"Wheat flour T55 French tradition (sac 25 kg)" → "Wheat flour T55 French tradition"."""
    return product_name.split(" (")[0].strip()


def franco_note(total_ht: float) -> str | None:
    """Below 150 € HT there is a 12 € delivery fee: worth saying, with what is missing."""
    if total_ht >= FRANCO_HT or total_ht <= 0:
        return None
    missing = FRANCO_HT - total_ht
    return (f"Delivery costs 12 euros for orders below 150 euros excluding VAT. "
            f"About {fr_number(round(missing))} more euros would qualify for free delivery.")


def unusual_lines(lines: list[dict], usual: list[dict], ratio: float = UNUSUAL_RATIO) -> list[dict]:
    """Lines at `ratio`× or more of the client's usual quantity for that product (a « 100 » heard for « 10 »…)."""
    avg = {u["productId"]: u.get("avgQty") or 0 for u in usual}
    out = []
    for line in lines:
        usual_qty = avg.get(line["productId"]) or 0
        if usual_qty > 0 and line["qty"] >= ratio * usual_qty:
            out.append({"productId": line["productId"], "qty": line["qty"], "usualQty": round(usual_qty, 1)})
    return out


def review(order: dict, products: dict[str, dict], usual: list[dict], client_orders: list[dict] | None = None) -> dict:
    """
    Everything to read back before confirm_order, deterministic:
      readback : "12 bags of wheat flour T55 French tradition, ...; delivery Thursday 26 November"
      alerts     : what to tell the caller (ERP warnings translated, internal ones dropped)
      franco     : the 12 € fee note when the order is below 150 € HT
      askFirst   : unusual quantities to have confirmed
      canConfirm : False when a warning blocks (client blocked, credit limit, no route, missing stock)
      duplicateDrafts / sameDayOrders : see other_open_orders (`client_orders` = the client's order list)
    """
    parts = []
    for line in order["lines"]:
        p = products.get(line["productId"]) or {}
        parts.append(f"{say_quantity(line['qty'], line.get('unit') or p.get('unit'), p.get('caliber'))} of {short_name(line.get('productName') or p.get('name', ''))}")
    when = french_day(date.fromisoformat(order["deliveryDate"][:10])) if order.get("deliveryDate") else None
    readback = ", ".join(parts) + (f", for delivery on {when}" if when else "")

    alerts: list[str] = []
    blocking: list[str] = []
    for w in order.get("warnings") or []:
        said, blocks = WARNINGS_FOR_CALLER.get(w.get("code"), (None, False))
        if w.get("code") == "insufficient_stock":
            line = next((li for li in order["lines"] if li["productId"] == w.get("productId")), None)
            if line:
                p = products.get(line["productId"]) or {}
                left = max(0.0, line.get("available") or 0)
                said = (f"{short_name(line.get('productName', ''))}: only "
                        f"{say_quantity(left, line.get('unit') or p.get('unit'), p.get('caliber'))} left") if left > 0 else \
                    f"{short_name(line.get('productName', ''))}: out of stock"
        if said and said not in alerts:
            alerts.append(said)
        if blocks:
            blocking.append(w.get("code"))

    unusual = unusual_lines(order["lines"], usual)
    ask_first = []
    for u in unusual:
        p = products.get(u["productId"]) or {}
        name = short_name(p.get("name", u["productId"]))
        ask_first.append(f"{say_quantity(u['qty'], p.get('unit'), p.get('caliber'))} of {name}, compared with your usual "
                         f"{say_quantity(u['usualQty'], p.get('unit'), p.get('caliber'))}")
    out = {
        "orderId": order.get("id"),
        "readback": readback,
        "totalHt": order.get("totalHt"),
        "canConfirm": not blocking,
        "alerts": alerts,
        "askFirst": ask_first,
    }
    if note := franco_note(order.get("totalHt") or 0):
        out["franco"] = note
    if blocking:
        out["blockedBy"] = sorted(set(blocking))
    duplicates, same_day = other_open_orders(order, client_orders or [], products)
    if duplicates:
        out["duplicateDrafts"] = duplicates
    if same_day:
        out["sameDayOrders"] = same_day
    return out


OPEN = ("draft", "confirmed", "prepared")


def other_open_orders(order: dict, client_orders: list[dict], products: dict[str, dict] | None = None) -> tuple[list[dict], list[dict]]:
    """
    The client's other orders that matter before confirming `order`:
      duplicates : other DRAFTS created by the voice agent (a draft left behind when the agent re-created the order
                   instead of editing it: the very bug seen in S31 v1) → to cancel before confirm_order.
      same_day   : other open orders for the same delivery day (e.g. a WhatsApp draft the client sent last night)
                   → to mention: "You already have an order for Wednesday, do I add it in?".
    Drafts from other channels (WhatsApp, e-mail, portal) are never duplicates: the team confirms those.
    """
    duplicates, same_day = [], []
    for o in client_orders:
        if o.get("id") == order.get("id") or o.get("status") not in OPEN:
            continue
        brief = {"orderId": o["id"], "number": o.get("number"), "status": o["status"], "deliveryDate": o.get("deliveryDate"),
                 "source": o.get("source"), "totalHt": o.get("totalHt")}
        if o["status"] == "draft" and o.get("source") == "voice_agent":
            if o.get("lines") is not None:  # detail given by the tool: say what it holds, and whether it is the same order
                brief["readback"] = ", ".join(_line_words(li, products or {}) for li in o["lines"])
                brief["sameAsThis"] = _qty_by_product(o["lines"]) == _qty_by_product(order["lines"])
            duplicates.append(brief)
        elif o.get("deliveryDate") == order.get("deliveryDate"):
            same_day.append(brief)
    return duplicates, same_day


def _qty_by_product(lines: list[dict]) -> dict[str, float]:
    acc: dict[str, float] = {}
    for li in lines:
        acc[li["productId"]] = acc.get(li["productId"], 0) + li["qty"]
    return acc


def _line_words(line: dict, products: dict[str, dict]) -> str:
    p = products.get(line["productId"]) or {}
    return f"{say_quantity(line['qty'], line.get('unit') or p.get('unit'), p.get('caliber'))} of {short_name(line.get('productName') or p.get('name', ''))}"


# ── Prices said out loud (S05 recording: « 92 euros la plaque de 2 kilos… pardon, 18 euros 40 ») ──
# The model multiplied in its head and got it wrong on the phone. The arithmetic is done here, the model only says it.

_FR_WORD_UNITS = {"kg": "kilo", "l": "litre"}


def fr_money(x: float) -> str:
    """ 9.2 → "9 euros 20", 92.0 → "92 euros", 0.5 → "50 centimes", 1.05 → "1 euro 05"."""
    cents = round(x * 100)
    e, c = divmod(cents, 100)
    if e == 0:
        return f"{c} cent{'s' if c != 1 else ''}"
    euros = f"{e} euro{'s' if e > 1 else ''}"
    return f"{euros} and {c} cent{'s' if c != 1 else ''}" if c else euros


def packaging(unit: str, caliber: str, product_name: str = "") -> list[tuple[str, float]]:
    """
    The packages a weighed / liquid product is handled in, biggest first, with their size in the selling unit:
      kg, "carton 5 plates of 2 kg" → [("carton", 10), ("plate", 2)]
      kg, "platelet 1 kg" (name "... (cardboard 10 × 1 kg)") → [("cardboard", 10), ("platelet", 1)]
      read, "carton 6 × 1 L" (name "... (brick 1 L)") → [("carton", 6), ("brick", 1)]
      kg, "sac 5 kg"                                       → [("sac", 5)]
    Products sold by the piece / box (sacs de farine, cartons de viennoiserie) return [] : the unit IS the package.
    """
    if unit not in ("kg", "liter", "l"):
        return []
    out: list[tuple[str, float]] = []

    def num(s: str) -> float:
        return float(s.replace(",", "."))

    texts = [_norm(t.replace("×", "x")) for t in [caliber, *re.findall(r"\(([^)]*)\)", product_name)]]  # _norm drops "×"
    for t in texts:
        t = re.sub(r"^(\d+(?:[.,]\d+)?\s*(?:x\s*\d+(?:[.,]\d+)?\s*)?(?:kg|l))\s+(\w+)$", r"\2 \1", t)
        t = re.sub(r"^(box|carton|case|pack|sack|bag) of ", r"\1 ", t)
        if m := re.match(r"^(\w+)\s+(\d+)\s+(\w+?)s?\s+(?:of|de)\s+(\d+(?:[.,]\d+)?)\s*(kg|l)\b", t):  # carton 5 plaques de 2 kg
            out += [(m[1], int(m[2]) * num(m[4])), (m[3], num(m[4]))]
        elif m := re.match(r"^(\w+)\s+(\d+)\s*[x×]\s*(\d+(?:[.,]\d+)?)\s*(kg|l)\b", t):  # carton 6 × 1 L
            out.append((m[1], int(m[2]) * num(m[3])))
        elif m := re.match(r"^(\w+)\s+(\d+(?:[.,]\d+)?)\s*(kg|l)\b", t):  # sac 5 kg, brique 1 L
            out.append((m[1], num(m[2])))
    seen, uniq = set(), []
    for word, size in sorted(out, key=lambda p: -p[1]):
        if word not in seen:
            seen.add(word)
            uniq.append((word, size))
    return uniq


def to_selling_qty(qty: float, said_unit: str | None, unit: str, caliber: str, product_name: str = "") -> float:
    """What the caller said → quantity in the product's selling unit: 3 cartons of tourage → 30 (kg), 50 kg of flour → 2 sacks."""
    said = _said(said_unit)
    if unit in ("kg", "liter", "l"):
        if said is None or said in ("kg", "l"):
            return qty
        word = said.rstrip("sx") if said.endswith(("s", "x")) and said not in ("box",) else said
        if said == 'boxes':
            word = 'box'
        for w, size in packaging(unit, caliber, product_name):
            if w == word or w == said:
                return round(qty * size, 3)
        return qty
    return sacks_from_words(caliber, qty, said_unit)


def quote(qty: float, unit: str, caliber: str, product_name: str, unit_price: float, said_unit: str | None = None) -> dict:
    """
    Price sentences ready to be said, computed (never by the model):
      Say: "9 euros 20 per kilo, or 92 euros a 10 kilo carton (18 euros 40 a 2 kilo plaque)"
      Total: "€276 excluding taxes for 30 kg, i.e. 3 cartons"
    """
    q = to_selling_qty(qty, said_unit, unit, caliber, product_name)
    word = _FR_WORD_UNITS.get("l" if unit == "liter" else unit)
    packs = packaging(unit, caliber, product_name)
    if word:
        say = f"{fr_money(unit_price)} per {word}"
        for package, size in packs:
            if size != 1:
                say += f", {fr_money(unit_price * size)} per {fr_number(size)}-{word} {package}"
    else:
        say = f"{fr_money(unit_price)} per {caliber or 'piece'}"


    total = unit_price * q
    qty_words = say_quantity(q, unit, caliber)
    if word and packs and (n := q / packs[0][1]) == int(n) and n >= 1:
        qty_words += f", or {fr_number(n)} {_plural(packs[0][0], n)}"
    return {
        "qty": q,
        "unitPrice": unit_price,
        "say": say,
        "total": f"{fr_money(total)} excluding VAT for {qty_words}",
        "totalHt": round(total, 2),
    }


# ── Jev (decision model): "is that a real yes?" and "which product?" (tools/order_jev.py) ──
# Calibrated on 12 real caller answers (mar. 24/11, 113–229 ms each): plain yeses score 0.89–0.96 on « accord »;
# « oui mais… », « et rajoutez… », « attendez », questions score ≤ 0.14, with « change » 0.59–0.93.

YES_MIN = 0.8  # « accord » at or above (and « change » below CHANGE_MIN): confirm
SURE_YES = 0.9  # « accord » at or above: confirm whatever « change » says
NO_MAX = 0.3  # « accord » at or below: do not confirm
CHANGE_MIN = 0.5  # « change » at or above (with no accord): the caller wants something modified
PICK_MIN = 0.6  # Jev's confidence needed to pick a product without asking

# Words the product glossary (03-glossaire-produits.md, « Alias ambigus ») says must be clarified: never settled by an
# alias alone, always by the client's habits (Jev) or by asking.
AMBIGUOUS_WORDS = {"laminating butter", "butter", "milk", "powder", "flour", "chocolate", "cream", "tourage", "lait", "poudre", "farine", "chocolat", "creme"}
_ARTICLES = re.compile(r"^(?:(?:some|the|an|a|du|de la|des|de|le|la|les|un|une)\s+|de l'|d'|l')")  # not the "de" of « demi-sel »


def _singular(s: str) -> str:
    return " ".join(w[:-1] if len(w) > 3 and w.endswith(("s", "x")) else w for w in s.split())


def alias_match(said: str, products: dict[str, dict]) -> str | None:
    """
    "Breads of yeast" → prd_0011 when the words are exactly one product's catalogue alias (or name before the
    parenthesis), singular/plural and accents ignored. None when no alias matches, when several products share it, or
    when it is one of the glossary's ambiguous words (« tourage », « poudre »…): those need the client's habits.
    """
    core = _singular(_ARTICLES.sub("", _norm(said)))
    if not core or core in AMBIGUOUS_WORDS:
        return None
    hits = {
        pid
        for pid, p in products.items()
        if p.get("active", True)
        and any(_singular(_ARTICLES.sub("", _norm(a))) == core for a in [*(p.get("aliases") or []), p.get("name", "").split(" (")[0]])
    }
    return next(iter(hits)) if len(hits) == 1 else None

JEV_YES_QUESTIONS = {
    "accord": {"type": "noul", "instructions": "The customer accepts the order as it has been reread, without changing anything."},
    "change": {"type": "noul", "instructions": "The client requests a change, an addition or a question before validating."},
}


def classify_answer(accord: float, change: float) -> str:
    """Jev's two probabilities → "yes" | "change" | "no" | "unsure"."""
    # A very clear yes wins: « C'est bon, validez » right after a price question scored accord 0.95 / change 0.55
    # (the question nudges « change » up). A real « oui mais… » never scored accord above 0.14 in the calibration.
    if accord >= SURE_YES or (accord >= YES_MIN and change < CHANGE_MIN):
        return "yes"
    if accord <= NO_MAX:
        return "change" if change >= CHANGE_MIN else "no"
    return "unsure"


NEXT_STEP = {
    "change": "The customer wants to modify or ask for something: answer him, change the order (update_order_line...), read again, then ask for his consent.",
    "no": "The client does not validate: do not confirm, ask him what he wishes (change, postpone or give up: cancel_draft_order).",
    "unsure": "Ambiguous answer: do not confirm, simply ask \"I validate it to you?\".",
}
