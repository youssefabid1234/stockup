"""Stock: lots (FEFO), computed stock levels, movements, manual adjustments.

    onHand    = Σ lot.qtyRemaining
    reserved  = Σ (preparedQty ?? qty) of lines of orders in status confirmed | prepared
    available = onHand − reserved
    incoming  = Σ (qty − receivedQty) of purchase orders sent | partially_received
"""

from __future__ import annotations

from collections.abc import Sequence
from itertools import islice

from app import crud
from app.core.activity import Ctx, log_event, now, today
from app.core.db import Doc, per_data_version, transactional
from app.core.listing import Key, ListQuery, apply_sort, respond, sort_rows
from app.core.errors import bad_request
from app.core.utils import add_days, cmp, collate_key, js_str, normalize, round3, sort_by

RESERVING_STATUSES = {"confirmed", "prepared"}


def line_qty(line: Doc) -> float:
    """Quantity a line weighs on stock: what was actually picked if known, else what was ordered."""
    prepared = line.get("preparedQty")
    return prepared if prepared is not None else line["qty"]


def fefo_lots(product_id: str) -> list[Doc]:
    """Lots of a product still holding stock, in FEFO order (first expired, first out)."""
    return list(_fefo_index().get(product_id, []))


@per_data_version
def _fefo_index() -> dict[str, list[Doc]]:
    """productId → its lots holding stock, FEFO order (one pass over the lots, cached until the next write)."""
    out: dict[str, list[Doc]] = {}
    for l in crud.lots.rows.values():
        if l["qtyRemaining"] > 0:
            out.setdefault(l["productId"], []).append(l)
    for lots in out.values():
        lots.sort(key=lambda l: (l["expiresAt"], l["receivedAt"]))
    return out


def stock_levels(exclude_order_id: str | None = None) -> dict[str, Doc]:
    """Stock level of every product (cached until the next write; never mutate the result).
    `exclude_order_id` computes availability without counting that order's own reservation."""
    return _compute_levels(exclude_order_id) if exclude_order_id else _all_levels()


@per_data_version
def _all_levels() -> dict[str, Doc]:
    return _compute_levels(None)


def _compute_levels(exclude_order_id: str | None) -> dict[str, Doc]:
    levels: dict[str, Doc] = {}

    def get(product_id: str) -> Doc:
        if product_id not in levels:
            levels[product_id] = {"productId": product_id, "onHand": 0, "reserved": 0, "available": 0, "incoming": 0, "lots": []}
        return levels[product_id]

    for product_id in crud.products.rows:
        get(product_id)
    for lot in crud.lots.rows.values():
        if lot["qtyRemaining"] <= 0:
            continue
        level = get(lot["productId"])
        level["onHand"] += lot["qtyRemaining"]
        level["lots"].append(lot)
    for order in crud.orders.rows.values():
        if order["status"] not in RESERVING_STATUSES or order["id"] == exclude_order_id:
            continue
        for line in order["lines"]:
            get(line["productId"])["reserved"] += line_qty(line)
    for po in crud.purchase_orders.rows.values():
        if po["status"] not in ("sent", "partially_received"):
            continue
        for line in po["lines"]:
            get(line["productId"])["incoming"] += max(0, line["qty"] - line["receivedQty"])
    for level in levels.values():
        level["lots"] = sort_by(level["lots"], lambda a, b: cmp(a["expiresAt"], b["expiresAt"]))
        level["onHand"] = round3(level["onHand"])
        level["reserved"] = round3(level["reserved"])
        level["incoming"] = round3(level["incoming"])
        level["available"] = round3(level["onHand"] - level["reserved"])
        if level["lots"]:
            level["nextExpiry"] = level["lots"][0]["expiresAt"]
    return levels


def stock_level(product_id: str) -> Doc:
    crud.products.require(product_id)
    return stock_levels()[product_id]


def _low_ids() -> set[str]:
    from app.services.dashboard import low_stock_ids  # (dashboard imports this module)

    return low_stock_ids()


STOCK_SORTS: dict[str, Key] = {
    "product": lambda r: collate_key(r["product"]["name"]),
    "sku": lambda r: r["product"]["sku"],
    "category": lambda r: r["product"]["category"],
    "onHand": lambda r: r["onHand"],
    "reserved": lambda r: r["reserved"],
    "available": lambda r: r["available"],
    "incoming": lambda r: r["incoming"],
    "expiry": lambda r: r.get("nextExpiry"),
    "state": lambda r: 0 if r["available"] <= 0 else 1 if r["productId"] in _low_ids() else 2,
}


def list_stock(lq: ListQuery | None = None, q: str | None = None, tab: str | None = None) -> list[Doc] | Doc:
    """GET /api/stock — every product's level with the product embedded, by product name.
    tab: out (available ≤ 0) | low (available > 0 but < 2 days of sales, same rule as the dashboard) |
    expiring (next expiry within 2 days). Envelope extras: counts per tab (ignoring `tab`; "" = all)."""
    lq = lq or ListQuery()
    levels = stock_levels()
    t = today()
    soon = add_days(t, 2)
    low = _low_ids()
    nq = normalize(q) if q else None
    tests = {
        "out": lambda r: r["available"] <= 0,
        "low": lambda r: r["available"] > 0 and r["productId"] in low,
        "expiring": lambda r: bool(r.get("nextExpiry")) and r["nextExpiry"] <= soon,
    }
    base = [
        {**levels[p["id"]], "product": p}
        for p in crud.products.all()
        if not nq or nq in normalize(f"{p['name']} {p['sku']} {' '.join(p['aliases'])}")
    ]
    base = sort_rows(base, STOCK_SORTS["product"])
    rows = [r for r in base if tests[tab](r)] if tab in tests else base
    rows = apply_sort(rows, lq, STOCK_SORTS)
    return respond(rows, lq, None, lambda: {"counts": {"": len(base), **{k: sum(1 for r in base if f(r)) for k, f in tests.items()}}})


class _MovementIndex:
    """Stock movements are append-only and stored in chronological order: index them once (all + per product,
    oldest first) and extend the index with the rows appended since, instead of re-sorting 400 k rows per request."""

    def __init__(self) -> None:
        self.rows_obj: object = None
        self.seen = 0
        self.all: list[Doc] = []
        self.by_product: dict[str, list[Doc]] = {}

    def get(self) -> "_MovementIndex":
        rows = crud.stock_movements.rows
        if rows is not self.rows_obj or len(rows) < self.seen:  # reloaded / reset → rebuild
            self.rows_obj, self.seen, self.all, self.by_product = rows, 0, [], {}
            fresh = sorted(rows.values(), key=lambda m: m["at"])
        else:
            fresh = list(islice(rows.values(), self.seen, None)) if len(rows) > self.seen else []
        for m in fresh:
            self.all.append(m)
            self.by_product.setdefault(m["productId"], []).append(m)
        self.seen = len(rows)
        return self


_movements = _MovementIndex()


class _Newest(Sequence):
    """Read-only newest-first view of an oldest-first list (no copy)."""

    def __init__(self, items: list[Doc]) -> None:
        self.items = items

    def __len__(self) -> int:
        return len(self.items)

    def __getitem__(self, i):  # type: ignore[override]
        if isinstance(i, slice):
            start, stop, _ = i.indices(len(self.items))
            n = len(self.items)
            return [self.items[n - 1 - k] for k in range(start, stop)]
        return self.items[len(self.items) - 1 - i]


def list_movements(product_id: str | None = None, limit: int = 100, lq: ListQuery | None = None) -> list[Doc] | Doc:
    """GET /api/stock/movements — newest first (`order=asc` for oldest first)."""
    lq = lq or ListQuery(limit=limit)
    idx = _movements.get()
    items = idx.by_product.get(product_id, []) if product_id else idx.all
    rows = items if lq.order == "asc" else _Newest(items)
    return respond(rows, lq)  # type: ignore[arg-type]


def _write_movement(m: Doc) -> Doc:
    return crud.stock_movements.put({"id": crud.stock_movements.next_id("mov_"), "at": now(), **m})


def _ref(ref: Doc) -> Doc:
    """Only the reference fields that are set (refType, refId, note)."""
    return {k: ref[k] for k in ("refType", "refId", "note") if ref.get(k) is not None}


def consume_fefo(product_id: str, qty: float, reason: str, ref: Doc) -> float:
    """Take `qty` out of stock following FEFO: one negative movement per lot touched.
    Returns the quantity that could NOT be taken (0 when stock was sufficient)."""
    left = qty
    for lot in fefo_lots(product_id):
        if left <= 0:
            break
        take = round3(min(lot["qtyRemaining"], left))
        crud.lots.put({**lot, "qtyRemaining": round3(lot["qtyRemaining"] - take)})
        _write_movement({"productId": product_id, "lotId": lot["id"], "qty": -take, "reason": reason, **_ref(ref)})
        left = round3(left - take)
    return max(0, left)


def add_lot(product: Doc, qty: float, reason: str, ref: Doc) -> Doc:
    """Create a new lot (receipt or positive adjustment) and its + movement. Expiry = today + shelf life."""
    received_at = today()
    lot = {
        "id": crud.lots.next_id("lot_"),
        "productId": product["id"],
        **({"supplierId": ref["supplierId"]} if ref.get("supplierId") else {}),
        **({"purchaseOrderId": ref["purchaseOrderId"]} if ref.get("purchaseOrderId") else {}),
        "qtyReceived": qty,
        "qtyRemaining": qty,
        "receivedAt": received_at,
        "expiresAt": add_days(received_at, product["shelfLifeDays"]),
    }
    crud.lots.put(lot)
    _write_movement({"productId": product["id"], "lotId": lot["id"], "qty": qty, "reason": reason, **_ref(ref)})
    return lot


@transactional
def adjust_stock(ctx: Ctx, input: Doc) -> Doc:
    """Manual correction. qty > 0 adds a lot (inventory found), qty < 0 removes FEFO.
    "waste" is always an exit, whatever the sign sent."""
    product = crud.products.require(input["productId"])
    qty = -abs(input["qty"]) if input["reason"] == "waste" else input["qty"]
    if qty == 0:
        raise bad_request("invalid_qty", "La quantité doit être différente de 0")
    ref = {"refType": "manual", "note": input.get("note")}
    if qty > 0:
        add_lot(product, qty, input["reason"], ref)
    else:
        missing = consume_fefo(product["id"], -qty, input["reason"], ref)
        qty = -round3(-qty - missing)
    label = "Perte" if input["reason"] == "waste" else "Ajustement"
    sign = "+" if qty > 0 else ""
    log_event(ctx, f"stock.{input['reason']}", "stock", product["id"],
              f"{label} de stock : {sign}{js_str(qty)} {product['unit']} de {product['name']}")  # fmt: skip
    return stock_level(product["id"])
