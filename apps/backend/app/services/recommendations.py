"""Offers supported by purchases, the catalogue and the price actually applied by the ERP."""

import re
from collections import Counter, defaultdict

from app import crud
from app.core.activity import Ctx, today
from app.core.db import Doc, per_data_version, transactional
from app.core.errors import conflict
from app.core.utils import add_days, normalize, weekday_of
from app.services import client_events, clients, orders, pricing, routing, stock

HISTORY_DAYS = 60
OFFER_REJECTED = "Offre refusée"
_open_issues = per_data_version(client_events.open_issues_by_client)


def eligible(client: Doc) -> bool:
    return client["status"] == "active" and not _open_issues().get(client["id"])


def _blocked_category(client: Doc, product: Doc) -> bool:
    # A catalogue novelty can otherwise be heard as an unwanted change of reference.
    text = normalize(" ".join([client.get("preferences") or "", *(n.get("text", "") for n in client.get("notes") or [])]))
    category = normalize(product["category"]).replace("-", " ")
    restrictions = ("pas de substitut", "jamais de substitut", "refuse", "uniquement", "seulement", "no substitut", "only")
    names = {normalize(product["name"]), category, *category.split()}
    names -= {"", "de", "et", "and", "les"}
    return any(word in text for word in restrictions) and any(name in text for name in names)


@per_data_version
def _basket_history() -> dict[str, list[tuple[str, set[str]]]]:
    day = today()
    since = add_days(day, -HISTORY_DAYS)
    history = defaultdict(list)
    for order in orders.orders_newest_first():
        delivery = order["deliveryDate"]
        if delivery < since:
            break
        previous = history[order["clientId"]]
        if delivery <= day and len(previous) < 40 and order["status"] in {"delivered", "invoiced"}:
            previous.append((delivery, {line["productId"] for line in order["lines"]}))
    return history


def _declined(client_id: str) -> set[str]:
    return {
        e.get("description", "")
        for e in crud.client_events.rows.values()
        if e["clientId"] == client_id and e.get("title") == OFFER_REJECTED and e["at"][:10] >= add_days(today(), -30)
    }


def quote(client: Doc, product: Doc, qty: float, delivery: str) -> Doc | None:
    day = today()
    if (
        not product["active"] or delivery < day or weekday_of(delivery) not in client.get("deliveryDays", [])
        or not routing.zone_served_on(client['zone'], delivery) or qty <= 0 or _blocked_category(client, product)
    ):
        return None
    level = stock.stock_levels().get(product["id"], {})
    on_time = sum(lot["qtyRemaining"] for lot in level.get("lots", []) if lot["expiresAt"] >= delivery)
    if on_time - level.get("reserved", 0) < qty:
        return None
    # Orders resolve tariff rules on the ERP business date. Also check that an announced promo
    # is still valid on the proposed delivery date, so it can safely be repeated in a follow-up.
    resolved = pricing.resolve_price(client["id"], product["id"], qty, day)
    candidate = next((c for c in resolved["candidates"] if c.get("applied")), {})
    rule = crud.price_rules.get(candidate.get("ruleId", "")) or {}
    until = rule.get("validTo")
    promo = bool(until and delivery <= until and resolved["price"] < resolved["listPrice"])
    return {
        "productId": product["id"], "productName": product["name"], "unit": product["unit"],
        "caliber": product.get("caliber"), "quantity": qty, "unitPrice": resolved["price"],
        "deliveryDate": delivery, "ruleId": rule["id"] if promo else None, "validUntil": until if promo else None,
    }


def select(client_id: str, order_id: str | None = None, product_id: str | None = None, *, outbound: bool = False) -> list[Doc]:
    client = crud.clients.require(client_id)
    if not eligible(client):
        return []
    order = crud.orders.get(order_id) if order_id else None
    if order_id and (not order or order["clientId"] != client_id or order["status"] != "draft"):
        return []
    delivery = order["deliveryDate"] if order else clients.next_delivery_date(client)
    basket = {line["productId"] for line in order["lines"]} if order else set()
    history = _basket_history().get(client_id, [])
    counts = Counter(pid for _, items in history for pid in items)
    categories = {
        row["category"] for pid, n in counts.items()
        if n >= 2 and (row := crud.products.get(pid))
    }
    refused = _declined(client_id)
    ranked = []
    new_since = add_days(today(), -30)
    for product in crud.products.rows.values():
        pid = product["id"]
        if pid in basket or (product_id and pid != product_id):
            continue
        launched = product.get("launchedOn")
        novelty = bool(launched and new_since <= launched <= today() and product["category"] in categories and not counts[pid])
        shared = sum(pid in items and bool(basket & items) for _, items in history) if basket else 0
        if counts[pid] < 2 and not novelty:
            continue
        # Start at the ERP sale unit. For a documented kg/l package use the package conversion.
        quantity = package_quantity(product)
        offer = quote(client, product, quantity, delivery)
        if not offer:
            continue
        if offer["ruleId"] and counts[pid] >= 2:
            kind, weight, key = "promo", 3, offer["ruleId"]
        elif novelty:
            kind, weight, key = "new", 2, launched
        elif shared >= 2 and not outbound:
            kind, weight, key = "usual", 1, "basket"
        else:
            continue
        offer_id = f"{kind}:{pid}:{key}"
        if offer_id in refused:
            continue
        last = next((day for day, items in history if pid in items), "")
        ranked.append(((weight, shared, counts[pid], last, pid), {
            **offer, "id": offer_id, "kind": kind, "purchaseCount": counts[pid],
            "coPurchaseCount": shared, "lastPurchasedOn": last or None,
        }))
    return [offer for _, offer in sorted(ranked, key=lambda pair: pair[0], reverse=True)[:5]]


def package_quantity(product: Doc) -> float:
    unit = product["unit"]
    if unit in {"kg", "liter"}:
        suffix = r"(?:kg|kilos?)" if unit == "kg" else r"l(?:itre)?s?"
        size = r"(\d+(?:[.,]\d+)?)"
        text = (product.get("caliber") or "").lower()
        text = re.sub(r"^carton of (\d+) (?:sheets|packs|blocks) of ", r"carton \1 x ", text)
        if match := re.match(r"^\w+\s+(\d+)\s+(?:\w+s?\s+de|[×x])\s*" + size + r"\s*" + suffix + r"\b", text):
            return int(match[1]) * float(match[2].replace(",", "."))
        if match := re.match(r"^\w+\s+" + size + r"\s*" + suffix + r"\b", text):
            return float(match[1].replace(",", "."))
    return 1


def fresh_offer(client_id: str, offer: Doc, order_id: str | None = None) -> Doc | None:
    return next((o for o in select(client_id, order_id, offer["productId"], outbound=not order_id) if o["id"] == offer["id"]), None)


@transactional
def add_offer(ctx: Ctx, client_id: str, offer: Doc, qty: float, order_id: str | None, request_id: str) -> Doc:
    key = f"{client_id}:{offer['id']}:{request_id}"
    if previous := crud.offer_additions.get(key):
        if previous["qty"] != qty or previous.get("originalOrderId") != order_id:
            raise conflict("offer_already_added", "Cette offre a déjà été ajoutée. Modifiez la ligne existante.")
        return orders.order_detail(previous["orderId"])
    fresh = fresh_offer(client_id, offer, order_id)
    if not fresh:
        raise conflict("offer_unavailable", "Cette offre n’est plus disponible.")
    client = crud.clients.require(client_id)
    product = crud.products.require(fresh["productId"])
    checked = quote(client, product, qty, fresh["deliveryDate"])
    if not checked or checked["unitPrice"] != offer["unitPrice"] or (fresh["kind"] == "promo" and checked["ruleId"] != offer["ruleId"]):
        raise conflict("offer_changed", "Le tarif ou le stock a changé pour cette quantité.")
    line = {"productId": product["id"], "qty": qty}
    if order_id:
        order = orders.add_line(ctx, order_id, line)
    else:
        order = orders.create_order(ctx, {
            "clientId": client_id, "deliveryDate": fresh["deliveryDate"], "lines": [line], "source": "voice_agent",
        })
    crud.offer_additions.put({"id": key, "qty": qty, "originalOrderId": order_id, "orderId": order["id"]})
    return order


def decline(ctx: Ctx, client_id: str, offer: Doc) -> None:
    if offer["id"] not in _declined(client_id):
        client_events.create_client_event(ctx, client_id, {
            "type": "call", "title": OFFER_REJECTED, "description": offer["id"], "productIds": [offer["productId"]],
        })
