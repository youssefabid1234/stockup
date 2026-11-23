"""Pricing: the ONE place a sell price is computed (order lines, quotes, the price grid, the AI tool).

Resolution (see PriceRule in app/schemas/domain.py):
  1. ClientPrice — explicit negotiated price client × product — always wins.
  2. PriceRule — the most specific applicable rule wins:
       client+product > client+group/category > client+all > clientGroup+product > clientGroup+group/category
       > clientGroup+all > all-clients rules (same product order);
     ties: higher priority, then most recent. A rule applies if active, within validFrom/validTo
     (on the pricing date) and qty ≥ minQty.
  3. Product.price — the list price.
Every matching candidate is returned with why it was or wasn't applied, plus a French explanation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app import crud
from app.core.activity import Ctx, log_event, now, today
from app.core.listing import ListQuery, respond
from app.core.db import Doc, transactional
from app.core.errors import bad_request
from app.core.utils import cmp, fmt_eur, js_round, js_str, locale_cmp, normalize, round2, sort_by
from app.services.tags import check_tags, tag_label
from app.services.categories import category_label



@dataclass
class PriceSubject:
    """Who we price for: a real client, or a client group (grid by group: no client-specific prices)."""

    client_id: str | None = None
    tags: list[str] = field(default_factory=list)


def _subject_of(client: Doc) -> PriceSubject:
    return PriceSubject(client_id=client["id"], tags=client.get("tags") or [])


# ───────── Scope matching ─────────


def _client_rank(scope: Doc, who: PriceSubject) -> int:
    if scope["kind"] == "client":
        return 2 if who.client_id == scope["clientId"] else -1
    if scope["kind"] == "tag":
        return 1 if scope["tag"] in who.tags else -1
    return 0


def _product_rank(scope: Doc, p: Doc) -> int:
    if scope["kind"] == "product":
        return 2 if p["id"] == scope["productId"] else -1
    if scope["kind"] == "tag":
        return 1 if scope["tag"] in (p.get("tags") or []) else -1
    if scope["kind"] == "category":
        return 1 if p["category"] == scope["category"] else -1
    return 0


def _specificity(rule: Doc, who: PriceSubject, p: Doc) -> int:
    """Client side first, then product side. -1 = the rule does not target this pair."""
    c = _client_rank(rule["clientScope"], who)
    pr = _product_rank(rule["productScope"], p)
    return -1 if c < 0 or pr < 0 else c * 3 + pr


def rule_price(rule: Doc, p: Doc) -> float:
    m = rule["method"]
    if m["kind"] == "fixed":
        return round2(m["price"])
    if m["kind"] == "discount_pct":
        return round2(p["price"] * (1 - m["pct"] / 100))
    return round2(p["cost"] * (1 + m["pct"] / 100))


def _inapplicable(rule: Doc, qty: float, date: str) -> str | None:
    """Why a rule that targets this pair does not apply (None = applicable)."""
    if not rule["active"]:
        return "règle inactive"
    if rule.get("validFrom") and date < rule["validFrom"]:
        return f"valable à partir du {rule['validFrom']}"
    if rule.get("validTo") and date > rule["validTo"]:
        return f"expirée le {rule['validTo']}"
    if rule.get("minQty") and qty < rule["minQty"]:
        return f"à partir de {js_str(rule['minQty'])} unités"
    return None


# ───────── Labels ─────────


def client_scope_label(s: Doc) -> str:
    if s["kind"] == "all":
        return "Tous les clients"
    if s["kind"] == "tag":
        return f"Groupe : {tag_label('client', s['tag'])}"
    client = crud.clients.get(s["clientId"])
    return client["name"] if client else s["clientId"]


def product_scope_label(s: Doc) -> str:
    if s["kind"] == "all":
        return "Tous les produits"
    if s["kind"] == "tag":
        return f"Groupe : {tag_label('product', s['tag'])}"
    if s["kind"] == "category":
        return f"Catégorie : {category_label(s['category'])}"
    product = crud.products.get(s["productId"])
    return product["name"] if product else s["productId"]


def method_label(m: Doc) -> str:
    if m["kind"] == "fixed":
        return f"Prix fixe {fmt_eur(m['price'])}"
    if m["kind"] == "discount_pct":
        return f"-{js_str(m['pct'])} % sur prix catalogue"
    return f"Coût +{js_str(m['pct'])} %"


def _margin(price: float, cost: float) -> float:
    return js_round((price - cost) / price * 10000) / 10000 if price > 0 else 0


# ───────── Resolver ─────────


def resolve_for_subject(who: PriceSubject, product: Doc, qty: float = 1, date: str | None = None) -> Doc:
    date = date or today()
    candidates: list[Doc] = []
    cp = crud.client_prices.get(f"{who.client_id}|{product['id']}") if who.client_id else None
    if cp:
        candidates.append({"source": "client_price", "label": "Prix négocié client", "price": round2(cp["price"]), "applied": False})

    ranked = [(r, _specificity(r, who, product)) for r in crud.price_rules.all()]
    ranked = sort_by(
        [x for x in ranked if x[1] >= 0],
        lambda a, b: cmp(b[1], a[1]) or cmp(b[0]["priority"], a[0]["priority"]) or cmp(b[0]["createdAt"], a[0]["createdAt"]),
    )
    rules = [r for r, _ in ranked]
    best: Doc | None = None
    for r in rules:
        reason = _inapplicable(r, qty, date)
        if not reason and not best:
            best = r
        label = f"Règle « {r['name']} » ({client_scope_label(r['clientScope'])} × {product_scope_label(r['productScope'])}, {method_label(r['method'])})"
        candidates.append({
            "source": "rule", "ruleId": r["id"], "label": label, "price": rule_price(r, product), "applied": False,
            **({"reason": reason} if reason else {}),
        })  # fmt: skip
    candidates.append({"source": "list", "label": "Prix catalogue", "price": round2(product["price"]), "applied": False})

    # Winner: client price > best applicable rule > list price.
    if cp:
        winner = candidates[0]
    elif best:
        winner = next(c for c in candidates if c.get("ruleId") == best["id"])
    else:
        winner = candidates[-1]
    winner["applied"] = True
    for c in candidates:
        if c["applied"] or c.get("reason"):
            continue
        if winner["source"] == "client_price":
            c["reason"] = "le prix négocié du client prime"
        else:
            c["reason"] = "remplacé par une règle" if c["source"] == "list" else "règle moins prioritaire"

    if winner["source"] == "client_price":
        explanation = f"Prix négocié pour ce client : {fmt_eur(winner['price'])}"
    elif best:
        explanation = (
            f"Règle « {best['name']} » ({client_scope_label(best['clientScope'])} × {product_scope_label(best['productScope'])}) : "
            f"{method_label(best['method'])} → {fmt_eur(winner['price'])}"
        )
    else:
        explanation = f"Prix catalogue : {fmt_eur(product['price'])}"
    if winner["source"] == "list" and rules:
        reasons = ", ".join(c.get("reason", "") for c in candidates if c["source"] == "rule")
        explanation += f" ({len(rules)} règle(s) non applicable(s) : {reasons})"

    return {
        "clientId": who.client_id or "",
        "productId": product["id"],
        "qty": qty,
        "price": winner["price"],
        "listPrice": product["price"],
        "cost": product["cost"],
        "marginPct": _margin(winner["price"], product["cost"]),
        "source": winner["source"],
        **({"ruleId": winner["ruleId"]} if winner.get("ruleId") else {}),
        "explanation": explanation,
        "candidates": candidates,
    }


def resolve_price(client_id: str, product_id: str, qty: float = 1, date: str | None = None) -> Doc:
    """GET /api/prices/resolve"""
    client = crud.clients.require(client_id)
    product = crud.products.require(product_id)
    if not qty > 0:  # also catches NaN
        raise bad_request("invalid_qty", "La quantité doit être positive")
    return resolve_for_subject(_subject_of(client), product, qty, date or today())


def price_for(client_id: str, product_id: str, qty: float = 1, date: str | None = None) -> float:
    """Just the number (order lines)."""
    return resolve_price(client_id, product_id, qty, date)["price"]


def price_grid(client_id: str | None = None, client_tag: str | None = None, product_tag: str | None = None,
               category: str | None = None, q: str | None = None) -> list[Doc]:  # fmt: skip
    """GET /api/prices/grid — resolved price (qty 1, today) of every active product for one client or one client group."""
    if client_id:
        who = _subject_of(crud.clients.require(client_id))
    elif client_tag:
        who = PriceSubject(tags=[client_tag])
    else:
        raise bad_request("missing_subject", "clientId ou clientTag requis")
    nq = normalize(q) if q else None
    day = today()
    products = crud.products.filter(
        lambda p: p["active"]
        and (not product_tag or product_tag in (p.get("tags") or []))
        and (not category or p["category"] == category)
        and (not nq or nq in normalize(f"{p['name']} {p['sku']} {' '.join(p['aliases'])}"))
    )
    rows = []
    for p in sort_by(products, lambda a, b: locale_cmp(a["name"], b["name"])):
        r = resolve_for_subject(who, p, 1, day)
        rows.append({
            "productId": p["id"], "productName": p["name"], "sku": p["sku"], "unit": p["unit"], "category": p["category"],
            "tags": p.get("tags") or [], "cost": p["cost"], "listPrice": p["price"], "price": r["price"], "source": r["source"],
            **({"ruleId": r["ruleId"]} if r.get("ruleId") else {}),
            "marginPct": r["marginPct"],
        })  # fmt: skip
    return rows


# ───────── Rules: list / CRUD ─────────


def rule_summary(r: Doc) -> Doc:
    cs = r["clientScope"]
    if cs["kind"] == "all":
        affected_clients = len(crud.clients.rows)
    elif cs["kind"] == "client":
        affected_clients = 1
    else:
        affected_clients = len(crud.clients.filter(lambda c: cs["tag"] in (c.get("tags") or [])))
    return {
        **r,
        "clientScopeLabel": client_scope_label(r["clientScope"]),
        "productScopeLabel": product_scope_label(r["productScope"]),
        "methodLabel": method_label(r["method"]),
        "affectedProducts": len(crud.products.filter(lambda p: _product_rank(r["productScope"], p) >= 0)),
        "affectedClients": affected_clients,
    }


def list_price_rules(active: str | None = None, client_id: str | None = None, product_id: str | None = None,
                     lq: ListQuery | None = None) -> list[Doc] | Doc:  # fmt: skip
    """GET /api/price-rules — clientId/productId keep the rules that target them."""
    client = crud.clients.require(client_id) if client_id else None
    product = crud.products.require(product_id) if product_id else None
    rules = crud.price_rules.filter(
        lambda r: (not active or r["active"] == (active == "true"))
        and (not client or _client_rank(r["clientScope"], _subject_of(client)) >= 0)
        and (not product or _product_rank(r["productScope"], product) >= 0)
    )
    rules = sort_by(rules, lambda a, b: cmp(b["priority"], a["priority"]) or cmp(b["createdAt"], a["createdAt"]))
    return respond(rules, lq or ListQuery(limit=10**9), rule_summary)


def _check_rule(r: Doc) -> None:
    cs, ps, m = r["clientScope"], r["productScope"], r["method"]
    if cs["kind"] == "client":
        crud.clients.require(cs["clientId"])
    if cs["kind"] == "tag":
        check_tags("client", [cs["tag"]])
    if ps["kind"] == "product":
        crud.products.require(ps["productId"])
    if ps["kind"] == "tag":
        check_tags("product", [ps["tag"]])
    if m["kind"] == "fixed" and not m["price"] > 0:
        raise bad_request("invalid_price", "Le prix fixe doit être positif")
    if m["kind"] == "discount_pct" and not 0 < m["pct"] < 100:
        raise bad_request("invalid_pct", "La remise doit être entre 0 et 100 %")
    if m["kind"] == "markup_pct" and not m["pct"] >= 0:
        raise bad_request("invalid_pct", "La marge sur coût doit être positive")
    if r.get("validFrom") and r.get("validTo") and r["validTo"] < r["validFrom"]:
        raise bad_request("invalid_dates", "validTo avant validFrom")


def _rule_entity(r: Doc) -> tuple[str, str]:
    """ActivityEvent entity for a rule: the client or product it targets, else "product" (prices changed)."""
    if r["clientScope"]["kind"] == "client":
        return "client", r["clientScope"]["clientId"]
    if r["productScope"]["kind"] == "product":
        return "product", r["productScope"]["productId"]
    return "product", r["id"]


@transactional
def create_price_rule(ctx: Ctx, input: Doc) -> Doc:
    _check_rule(input)
    rule = {
        **input,
        "id": crud.price_rules.next_id("prl_", 4),
        "active": input.get("active", True),
        "priority": input.get("priority", 0),
        "createdAt": now(),
    }
    crud.price_rules.put(rule)
    log_event(ctx, "price_rule.created", *_rule_entity(rule),
              f"Nouvelle règle de prix « {rule['name']} » : {method_label(rule['method'])} "
              f"({client_scope_label(rule['clientScope'])} × {product_scope_label(rule['productScope'])})")  # fmt: skip
    return rule


@transactional
def update_price_rule(ctx: Ctx, id: str, patch: Doc) -> Doc:
    rule = crud.price_rules.require(id)
    updated = {**rule, **patch}
    _check_rule(updated)
    crud.price_rules.put(updated)
    if patch.get("active") is False:
        what = "désactivée"
    elif patch.get("active") is True and not rule["active"]:
        what = "réactivée"
    else:
        what = f"modifiée ({', '.join(patch)})"
    log_event(ctx, "price_rule.updated", *_rule_entity(updated), f"Règle de prix « {updated['name']} » {what}")
    return updated


@transactional
def delete_price_rule(ctx: Ctx, id: str) -> Doc:
    rule = crud.price_rules.require(id)
    crud.price_rules.delete(id)
    log_event(ctx, "price_rule.deleted", *_rule_entity(rule), f"Règle de prix « {rule['name']} » supprimée")
    return {"ok": True}


# ───────── Negotiated client prices ─────────


@transactional
def set_client_price(ctx: Ctx, client_id: str, product_id: str, price: float) -> Doc:
    client = crud.clients.require(client_id)
    product = crud.products.require(product_id)
    if not price > 0:
        raise bad_request("invalid_price", "Le prix doit être positif")
    before = crud.client_prices.get(f"{client_id}|{product_id}")
    cp = crud.client_prices.put({"clientId": client_id, "productId": product_id, "price": round2(price)})
    was = f" (avant {fmt_eur(before['price'])})" if before else f" (catalogue {fmt_eur(product['price'])})"
    log_event(ctx, "client_price.set", "client", client_id,
              f"Prix négocié {product['name']} pour {client['name']} : {fmt_eur(cp['price'])}{was}")  # fmt: skip
    return cp


@transactional
def delete_client_price(ctx: Ctx, client_id: str, product_id: str) -> Doc:
    client = crud.clients.require(client_id)
    product = crud.products.require(product_id)
    key = f"{client_id}|{product_id}"
    crud.client_prices.require(key)
    crud.client_prices.delete(key)
    log_event(ctx, "client_price.deleted", "client", client_id, f"Prix négocié {product['name']} supprimé pour {client['name']}")
    return {"ok": True}
