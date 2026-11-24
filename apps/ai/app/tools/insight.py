"""
OWNER: Youssef · the logic behind the product_insight tool (no @tool here: importing this module registers nothing,
so tests and other bricks can use it whatever TEAM_PRODUCT_INSIGHT says).

Real life: when a baker asks for a product, Lucie glances at ONE screen: stock, the price for THIS client, and if it
is short, what to offer instead (in stock, the substitute the house recommends, with its promo). Here: every ERP read
in parallel, so the model gets everything in one round-trip instead of 4 to 6.

    wave 1 (parallel): product · this client's price · ERP alternatives · client card · price rules (cached)
    wave 2 (parallel, only if the product is short): this client's price for each alternative
    then: Daycem's substitution_policy (does the client accept a substitute?) and rank_alternatives (best first)

A promo = the price the ERP applies to this client comes from a price rule with an end date (validTo) and is below the
list price (e.g. Daycem's demo rule « Promo tourage 82 % : −8 % jusqu'au 30/11 »). Nothing is invented: no rule, no
promo (SALES_RULES: « Ne cite une promotion que si l'ERP en renvoie une »).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from .erp import enc

MAX_ALTERNATIVES = 5  # like find_alternatives: enough to choose, small enough for the model to read fast
RULES_TTL = 60.0  # seconds: price rules change rarely (Daycem's setup script, the back office)

_rules: tuple[float, dict[str, dict]] | None = None

# Added to the system prompt when TEAM_PRODUCT_INSIGHT is on (prompts.py): the model must know to prefer the tool.
PRODUCT_INSIGHT_RULE = """Outil produit (prime sur les règles qui citent get_product_stock, get_price ou find_alternatives) :
- Produit demandé : appelle product_insight UNE seule fois (client, produit, quantité dans l'unité du produit). Il donne déjà le stock, les arrivages attendus (incoming), le prix de CE client avec son explication et sa promo, et, si ça manque, les remplaçants classés (le premier est le meilleur) avec LEUR prix client et LEUR promo.
- Ensuite, n'appelle ni get_product_stock, ni get_price, ni find_alternatives, ni un second product_insight pour ce produit ou ses remplaçants : tout est dans la réponse. Un nouveau product_insight seulement pour un AUTRE produit ou une autre quantité.
- « substitution » : refuse = annonce la rupture, ne propose aucun autre produit ; accepte = propose le premier remplaçant ; demander ou inconnu = demande d'abord s'il veut un autre produit."""


def product_insight_section() -> str:
    from app import team_flags

    return PRODUCT_INSIGHT_RULE if team_flags.product_insight() else ""


def clear_cache() -> None:
    global _rules
    _rules = None


def _num(n: float | None) -> str | None:
    """5.0 → "5", 2.5 → "2.5" (the ERP's query format, like catalog.format_number)."""
    if n is None:
        return None
    return str(int(n)) if float(n).is_integer() else str(n)


async def _price_rules(erp) -> dict[str, dict]:
    """{rule id: rule}, cached a minute. {} if the ERP can't list them (then: no promo shown, never a wrong one)."""
    global _rules
    if _rules and time.monotonic() - _rules[0] < RULES_TTL:
        return _rules[1]
    try:
        rows = await erp.get("/api/price-rules", {"limit": 500})
    except Exception:
        return {}
    rows = rows.get("items", rows) if isinstance(rows, dict) else rows
    _rules = (time.monotonic(), {r["id"]: r for r in rows or [] if r.get("id")})
    return _rules[1]


def promo_of(resolved: dict | None, rules: dict[str, dict]) -> dict | None:
    """The promo behind a resolved price, or None. Promo = applied rule, time-limited (validTo), below the list price."""
    if not resolved or resolved.get("source") != "rule":
        return None
    price, list_price = resolved.get("price"), resolved.get("listPrice")
    if price is None or list_price is None or price >= list_price:
        return None
    applied = next((c for c in resolved.get("candidates") or [] if c.get("applied") and c.get("ruleId")), None)
    rule = rules.get(applied["ruleId"]) if applied else None
    if not rule or not rule.get("validTo"):
        return None  # a permanent group discount (« Boulangeries : −4 % … ») is a price, not a promo
    return {"name": rule.get("name"), "until": rule["validTo"], "pctOff": round((1 - price / list_price) * 100)}


def _volume_hint(resolved: dict) -> str | None:
    """A volume rule that would give a better price (like get_price's betterPriceWithVolume): worth telling."""
    for c in resolved.get("candidates") or []:
        if c.get("source") == "rule" and (c.get("reason") or "").startswith("à partir de") and c["price"] < resolved["price"]:
            return f"{_num(c['price'])} € {c['reason']}"
    return None


async def _resolve(erp, client_id: str, product_id: str, qty: float | None) -> dict | None:
    try:
        return await erp.get("/api/prices/resolve", {"clientId": client_id, "productId": product_id, "qty": _num(qty)})
    except Exception:  # one price failing must not hide the others
        return None


async def gather_insight(erp, client_id: str, product_id: str, qty: float | None = None) -> dict[str, Any]:
    """Everything about one product for one client, in one call. Shape: docs/team/interfaces.md §2."""
    from app.agent.rules_sales import has_same_use_substitute, rank_alternatives, substitution_policy

    async def safe(coro):
        try:
            return await coro
        except Exception:
            return None

    product, price, alternatives, client, rules = await asyncio.gather(
        erp.get(f"/api/products/{enc(product_id)}"),  # unknown product → ErpError: the model is told, as with any tool
        _resolve(erp, client_id, product_id, qty),
        safe(erp.get(f"/api/products/{enc(product_id)}/alternatives")),
        safe(erp.get(f"/api/clients/{enc(client_id)}")),
        _price_rules(erp),
    )
    available = product.get("available") or 0
    in_stock = available >= qty if qty else available > 0
    out: dict[str, Any] = {
        "product": {
            "id": product.get("id", product_id),
            "name": product.get("name"),
            "unit": product.get("unit"),
            "available": available,
            "clientPrice": price.get("price") if price else None,
            "listPrice": price.get("listPrice") if price else product.get("price"),
            "priceExplanation": price.get("explanation") if price else "prix client indisponible (ERP)",
        },
        "inStock": in_stock,
    }
    stock = product.get("stock") or {}
    if stock.get("incoming"):  # arrivals already expected (Daycem's rule: a solution that is not another product)
        out["product"]["incoming"] = stock["incoming"]
    if price and (promo := promo_of(price, rules)):
        out["product"]["promo"] = promo
    if price and (hint := _volume_hint(price)):
        out["product"]["betterPriceWithVolume"] = hint
    if in_stock:
        out["alternatives"] = []  # nothing to replace: keep the answer short (every byte is read by the model)
        return out

    if qty and available > 0:
        out["missing"] = round(qty - available, 3)  # partial: the caller may take what is there + a substitute
    card = client or {}
    # ERP notes are {at, author, text} (call_context.py reads them the same way); plain strings tolerated
    notes = [n.get("text") or "" if isinstance(n, dict) else str(n) for n in card.get("notes") or []]
    out["substitution"] = substitution_policy(product.get("name") or "", card.get("preferences") or "", notes)
    if out["substitution"] == "refuse":
        out["alternatives"] = []  # Daycem's rule: announce the shortage, offer no other product
        out["note"] = (
            "Ce client refuse les remplacements pour ce produit : annonce la rupture, ne propose aucun autre produit. "
            "Tu peux PROPOSER de noter sa demande pour le premier arrivage, mais n'enregistre rien avant son accord."
        )
        return out

    candidates = [a for a in alternatives or [] if a.get("id") and a.get("id") != product_id]
    if not has_same_use_substitute(product_id, product.get("name") or "", candidates):
        # Daycem's T3: nothing in stock has the same use (docs name none, no name in common): don't push lemons for
        # strawberries; no second wave of prices either
        out["alternatives"] = []
        out["note"] = (
            "Aucun produit en stock n'a le même usage. Annonce la rupture et demande au client ce qu'il souhaite, "
            "sans proposer de produit."
        )
        return out
    prices = await asyncio.gather(
        *(_resolve(erp, client_id, a["id"], qty if a.get("unit") == product.get("unit") else None) for a in candidates)
    )
    rows = []
    for a, p in zip(candidates, prices):
        row = {
            "id": a["id"],
            "name": a.get("name"),
            "unit": a.get("unit"),
            "available": a.get("available") or 0,
            "clientPrice": p.get("price") if p else None,
            "listPrice": p.get("listPrice") if p else a.get("price"),
            "category": a.get("category"),
        }
        if promo := promo_of(p, rules):
            row["promo"] = promo
        rows.append(row)
    ranked = rank_alternatives(
        rows, card.get("preferences") or "", for_product_id=product_id, for_category=product.get("category"),
        for_product_name=product.get("name"), for_unit=product.get("unit"),
    )
    out["alternatives"] = [{k: v for k, v in r.items() if k != "category"} for r in ranked[:MAX_ALTERNATIVES]]
    return out
