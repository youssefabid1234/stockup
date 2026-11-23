"""Catalogue reads: products (with stock), alternatives, suppliers."""

from __future__ import annotations

from app import crud
from app.core.activity import today
from app.core.db import Doc
from app.core.listing import Key, ListQuery, apply_sort, count_by, respond, sort_rows, split_set
from app.core.utils import add_days, cmp, collate_key, normalize, round2, round3, sort_by
from app.services import purchasing
from app.services.orders import orders_newest_first
from app.services.stock import list_movements, stock_levels
from app.services.supplier_events import supplier_history


def _product_summary(p: Doc, levels: dict[str, Doc]) -> Doc:
    level = levels.get(p["id"])
    return {
        **p,
        "available": level["available"] if level else 0,
        "onHand": level["onHand"] if level else 0,
        **({"nextExpiry": level["nextExpiry"]} if level and level.get("nextExpiry") else {}),
    }


PRODUCT_SORTS: dict[str, Key] = {
    "name": lambda p: collate_key(p["name"]),
    "sku": lambda p: p["sku"],
    "category": lambda p: p["category"],
    "tags": lambda p: ",".join(p.get("tags") or []),
    "price": lambda p: p["price"],
    "cost": lambda p: p["cost"],
    "margin": lambda p: (p["price"] - p["cost"]) / p["price"] if p["price"] > 0 else 0,
    "available": lambda p: stock_levels().get(p["id"], {}).get("available", 0),
    "expiry": lambda p: stock_levels().get(p["id"], {}).get("nextExpiry"),
}


def list_products(lq: ListQuery | None = None, q: str | None = None, category: str | None = None, tag: str | None = None,
                  active: str | None = None) -> list[Doc] | Doc:  # fmt: skip
    """GET /api/products — by name. Envelope extras: counts per category (ignoring `category`)."""
    lq = lq or ListQuery()
    levels = stock_levels()
    nq = normalize(q) if q else None
    categories = split_set(category)
    base = crud.products.filter(
        lambda p: (not tag or tag in (p.get("tags") or []))
        and (active is None or p["active"] == (active in ("true", "1")))
        and (not nq or nq in normalize(f"{p['name']} {p['sku']} {' '.join(p['aliases'])} {p.get('origin') or ''}"))
    )
    base = sort_rows(base, PRODUCT_SORTS["name"])
    rows = [p for p in base if p["category"] in categories] if categories else base
    rows = apply_sort(rows, lq, PRODUCT_SORTS)
    return respond(rows, lq, lambda p: _product_summary(p, levels), lambda: {"counts": count_by(base, lambda p: p["category"])})


def product_detail(id: str) -> Doc:
    p = crud.products.require(id)
    levels = stock_levels()
    since = add_days(today(), -30)
    qty = revenue = 0.0
    for o in orders_newest_first():  # newest delivery first: stop at the 30-day window
        if o["deliveryDate"] <= since:
            break
        if o["status"] in ("draft", "cancelled") or o["deliveryDate"] > today():
            continue
        for l in o["lines"]:
            if l["productId"] != id:
                continue
            q = l["preparedQty"] if l.get("preparedQty") is not None else l["qty"]
            qty += q
            revenue += q * l["unitPrice"]
    supplier_prices = []
    for sp in crud.supplier_prices.filter(lambda sp: sp["productId"] == id):
        s = crud.suppliers.get(sp["supplierId"])
        supplier_prices.append({**sp, "supplierName": s["name"] if s else "?"})
    return {
        **_product_summary(p, levels),
        "stock": levels[id],
        "supplierPrices": sort_by(supplier_prices, lambda a, b: cmp(a["price"], b["price"])),
        "movements": list_movements(id, 30),
        "sales30d": {"qty": round3(qty), "revenue": round2(revenue)},
    }


def alternatives(id: str) -> list[Doc]:
    """Substitutes when a product is short: same category, in stock, closest price first."""
    p = crud.products.require(id)
    levels = stock_levels()
    candidates = crud.products.filter(
        lambda x: x["id"] != id and x["active"] and x["category"] == p["category"] and levels.get(x["id"], {}).get("available", 0) > 0
    )
    candidates = sort_by(candidates, lambda a, b: cmp(abs(a["price"] - p["price"]), abs(b["price"] - p["price"])))
    return [_product_summary(x, levels) for x in candidates[:10]]


SUPPLIER_SORTS: dict[str, Key] = {
    "name": lambda s: collate_key(s["name"]),
    "city": lambda s: collate_key(s["city"]) if s.get("city") else None,
    "tags": lambda s: ",".join(s.get("tags") or []),
    "lead": lambda s: s["leadTimeDays"],
    "terms": lambda s: s["paymentTermsDays"],
    "min": lambda s: s["minOrderAmount"],
}


def list_suppliers(lq: ListQuery | None = None, tag: str | None = None, q: str | None = None, category: str | None = None) -> list[Doc] | Doc:
    """GET /api/suppliers — by name."""
    lq = lq or ListQuery()
    nq = normalize(q) if q else None
    suppliers = crud.suppliers.filter(
        lambda s: (not tag or tag in (s.get("tags") or []))
        and (not category or category in s["categories"])
        and (not nq or nq in normalize(f"{s['name']} {s['city']} {' '.join(c['name'] for c in s['contacts'])}"))
    )
    return respond(apply_sort(sort_rows(suppliers, SUPPLIER_SORTS["name"]), lq, SUPPLIER_SORTS), lq)


def supplier_detail(id: str) -> Doc:
    s = crud.suppliers.require(id)
    prices = []
    for sp in crud.supplier_prices.filter(lambda sp: sp["supplierId"] == id):
        p = crud.products.get(sp["productId"])
        prices.append({**sp, "productName": p["name"] if p else "?", "unit": p["unit"] if p else ""})
    pos = [po for po in purchasing.pos_newest_first() if po["supplierId"] == id]
    stats = {"count": len(pos), "openCount": 0, "openTotal": 0.0, "draftCount": 0, "doneCount": 0, "doneTotal": 0.0}
    for po in pos:
        if po["status"] in ("sent", "partially_received"):
            stats["openCount"] += 1
            stats["openTotal"] += po["totalHt"]
        if po["status"] == "draft":
            stats["draftCount"] += 1
        elif po["status"] != "cancelled":
            stats["doneCount"] += 1
            stats["doneTotal"] += po["totalHt"]
    stats["openTotal"], stats["doneTotal"] = round2(stats["openTotal"]), round2(stats["doneTotal"])
    return {
        **s,
        **supplier_history(id),
        "prices": prices,
        "purchaseOrders": [purchasing.po_summary(po) for po in pos[:60]],
        "purchaseStats": stats,
    }
