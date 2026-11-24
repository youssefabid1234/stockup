"""Sales orders and their lifecycle:

    draft ──confirm──▶ confirmed ──prepare──▶ prepared ──deliver──▶ delivered ──invoice──▶ invoiced
      │                    │                      │
      └───────cancel───────┴────────cancel────────┘                (deliver also accepted from confirmed)

- confirm reserves stock (reservation is computed from order statuses, see stock.py) and puts the
  order on a route run.
- deliver consumes lots FEFO and writes stock movements.
Illegal transitions raise 409 {code: "invalid_transition"}.
"""

from __future__ import annotations

import uuid

from app import crud
from app.core.activity import Ctx, log_event, now, today
from app.core.db import Doc, per_data_version, transactional
from app.core.listing import Key, ListQuery, apply_sort, count_by, respond, split_set, sum_of
from app.core.errors import bad_request, conflict
from app.core.utils import add_days, collate_key, de, fmt_eur, fr_day, fr_num, js_str, normalize, round2, round3, total
from app.services import clients, invoices, pricing, routing
from app.services.stock import consume_fefo, fefo_lots, line_qty, stock_levels

STATUS_FR = {
    "draft": "brouillon",
    "confirmed": "confirmée",
    "prepared": "préparée",
    "delivered": "livrée",
    "invoiced": "facturée",
    "cancelled": "annulée",
}


def _guard(order: Doc, allowed: list[str], action: str) -> None:
    """409 unless the order is in one of `allowed`."""
    if order["status"] not in allowed:
        expected = " ou ".join(STATUS_FR[s] for s in allowed)
        raise conflict(
            "invalid_transition",
            f"Impossible {de(action)} la commande {order['number']} : elle est {STATUS_FR[order['status']]} (attendu : {expected})",
        )


def _total_ht(lines: list[Doc]) -> float:
    return round2(total(line_qty(l) * l["unitPrice"] for l in lines))


def _total_ttc(lines: list[Doc]) -> float:
    def vat(product_id: str) -> float:
        p = crud.products.get(product_id)
        return p["vatRate"] if p else 0.055

    return round2(total(line_qty(l) * l["unitPrice"] * (1 + vat(l["productId"])) for l in lines))


def _save(order: Doc) -> Doc:
    """Save an order, recomputing its total."""
    return crud.orders.put({**order, "totalHt": _total_ht(order["lines"])})


# ───────── Reads ─────────


def order_summary(o: Doc) -> Doc:
    client = crud.clients.get(o["clientId"])
    summary = {k: v for k, v in o.items() if k != "lines"}
    return {**summary, "clientName": client["name"] if client else "?", "lineCount": len(o["lines"])}


def _client_name(client_id: str) -> str:
    c = crud.clients.get(client_id)
    return c["name"] if c else "?"


@per_data_version
def orders_newest_first() -> list[Doc]:
    """Every order, newest delivery date first (ties: newest created first). Cached until the next write."""
    return sorted(crud.orders.rows.values(), key=lambda o: (o["deliveryDate"], o["createdAt"]), reverse=True)


ORDER_SORTS: dict[str, Key] = {
    "number": lambda o: o["number"],
    "client": lambda o: collate_key(_client_name(o["clientId"])),
    "date": lambda o: o["deliveryDate"],
    "createdAt": lambda o: o["createdAt"],
    "lines": lambda o: len(o["lines"]),
    "total": lambda o: o["totalHt"],
    "status": lambda o: o["status"],
}


def list_orders(lq: ListQuery, status: str | None = None, client_id: str | None = None, date: str | None = None,
                q: str | None = None, source: str | None = None, ids: str | None = None) -> list[Doc] | Doc:  # fmt: skip
    """GET /api/orders — newest delivery date first. Filters on the stored orders, sort, slice, then build the
    summaries of the page. Envelope extras: counts per status (all filters but status), sums.totalHt."""
    statuses, sources, wanted = split_set(status), split_set(source), split_set(ids)
    nq = normalize(q) if q else None
    names: dict[str, str] = {}

    def matches_q(o: Doc) -> bool:
        cid = o["clientId"]
        if cid not in names:
            names[cid] = normalize(_client_name(cid))
        return nq in f"{normalize(o['number'])} {names[cid]}"

    candidates = [o for o in orders_newest_first() if o["id"] in wanted] if wanted and len(wanted) > 50 else (
        sorted((crud.orders.rows[i] for i in wanted if i in crud.orders.rows), key=lambda o: (o["deliveryDate"], o["createdAt"]), reverse=True)
        if wanted else orders_newest_first()
    )
    base = [
        o for o in candidates
        if (not client_id or o["clientId"] == client_id)
        and (not date or o["deliveryDate"] == date)
        and (not sources or o.get("source") in sources)
        and (not nq or matches_q(o))
    ]  # fmt: skip
    rows = [o for o in base if o["status"] in statuses] if statuses else base
    rows = apply_sort(rows, lq, ORDER_SORTS)
    return respond(rows, lq, order_summary, lambda: {
        "counts": count_by(base, lambda o: o["status"]),
        "sums": sum_of(rows, totalHt=lambda o: o["totalHt"]),
    })


def order_warnings(order: Doc) -> list[Doc]:
    """Non-blocking business warnings for an order still in progress.
    Stock is checked against availability WITHOUT this order's own reservation."""
    if order["status"] not in ("draft", "confirmed", "prepared"):
        return []
    warnings: list[Doc] = []
    client = crud.clients.require(order["clientId"])

    if client["status"] == "blocked":
        warnings.append({"code": "client_blocked", "message": f"Le client {client['name']} est bloqué"})
    if client["creditLimit"] > 0:
        outstanding = clients.client_balances(client["id"])["outstanding"]
        exposure = round2(outstanding + _total_ttc(order["lines"]))
        if exposure > client["creditLimit"]:
            warnings.append({
                "code": "credit_limit",
                "message": f"Plafond de crédit dépassé : encours {fmt_eur(outstanding)} + cette commande = {fmt_eur(exposure)} TTC "
                f"pour un plafond de {fmt_eur(client['creditLimit'])}",
            })  # fmt: skip
    if not routing.zone_served_on(client["zone"], order["deliveryDate"]):
        warnings.append({"code": "no_route", "message": f"Aucune tournée ne dessert la zone « {client['zone']} » {fr_day(order['deliveryDate'])}"})

    levels = stock_levels(order["id"])
    demand: dict[str, float] = {}
    for l in order["lines"]:
        demand[l["productId"]] = demand.get(l["productId"], 0) + line_qty(l)
    for product_id, qty in demand.items():
        p = crud.products.get(product_id)
        name = p["name"] if p else product_id
        available = levels[product_id]["available"] if product_id in levels else 0
        if available < qty:
            warnings.append({
                "code": "insufficient_stock",
                "productId": product_id,
                "message": f"Stock insuffisant pour {name} : {fr_num(round3(max(0, available)))} {p['unit'] if p else ''} "
                f"disponible(s) pour {fr_num(qty)} demandé(s)",
            })  # fmt: skip
        # The lot FEFO would pick first expires the day after delivery or sooner.
        lots = fefo_lots(product_id)
        if lots and lots[0]["expiresAt"] <= add_days(order["deliveryDate"], 1):
            warnings.append({
                "code": "expiring_soon",
                "productId": product_id,
                "message": f"{name} : le lot {lots[0]['id']} expire {fr_day(lots[0]['expiresAt'])}",
            })  # fmt: skip
    for l in order["lines"]:
        p = crud.products.get(l["productId"])
        if p and l["unitPrice"] < p["cost"]:
            warnings.append({
                "code": "price_below_cost",
                "productId": p["id"],
                "message": f"{p['name']} vendu {fmt_eur(l['unitPrice'])} sous le coût d'achat ({fmt_eur(p['cost'])})",
            })  # fmt: skip
    return warnings


def order_detail(id: str) -> Doc:
    order = crud.orders.require(id)
    levels = stock_levels()
    inv = crud.invoices.get(order["invoiceId"]) if order.get("invoiceId") else None
    lines = []
    for l in order["lines"]:
        p = crud.products.get(l["productId"])
        level = levels.get(l["productId"])
        lines.append({**l, "productName": p["name"] if p else "?", "unit": p["unit"] if p else "", "available": level["available"] if level else 0})
    return {
        **order,
        "client": crud.clients.require(order["clientId"]),
        "lines": lines,
        "warnings": order_warnings(order),
        **({"invoice": invoices.invoice_summary(inv)} if inv else {}),
    }


# ───────── Writes ─────────


def _build_line(client_id: str, input: Doc) -> Doc:
    product = crud.products.require(input["productId"])
    if not product["active"]:
        raise bad_request("product_inactive", f"Le produit {product['name']} n'est plus actif")
    if not input["qty"] > 0:
        raise bad_request("invalid_qty", "La quantité doit être positive")
    unit_price = input.get("unitPrice")
    if unit_price is None:
        unit_price = pricing.price_for(client_id, product["id"], input["qty"])
    return {
        "id": f"lin_{uuid.uuid4().hex[:8]}",
        "productId": product["id"],
        "qty": input["qty"],
        "unitPrice": round2(unit_price),
        **({"note": input["note"]} if input.get("note") else {}),
        **({"substituteFor": input["substituteFor"]} if input.get("substituteFor") else {}),
    }


@transactional
def create_order(ctx: Ctx, input: Doc) -> Doc:
    client = crud.clients.require(input["clientId"])
    t = today()
    order = {
        "id": crud.orders.next_id("ord_"),
        "number": crud.orders.next_number("CMD", t[:4]),
        "clientId": client["id"],
        "status": "draft",
        "source": input.get("source") or ("voice_agent" if ctx.actor == "voice_agent" else "manual"),
        "deliveryDate": input.get("deliveryDate") or clients.next_delivery_date(client),
        "lines": [_build_line(client["id"], l) for l in input.get("lines") or []],
        "totalHt": 0,
        **({"note": input["note"]} if input.get("note") else {}),
        "createdAt": now(),
        "createdBy": ctx.actor_name or ctx.actor,
    }
    saved = _save(order)
    log_event(ctx, "order.created", "order", order["id"],
              f"Commande {order['number']} créée pour {client['name']} (livraison {order['deliveryDate']}, {len(order['lines'])} ligne(s))")  # fmt: skip
    return order_detail(saved["id"])


@transactional
def update_order(ctx: Ctx, id: str, patch: Doc) -> Doc:
    order = crud.orders.require(id)
    _guard(order, ["draft", "confirmed"], "modifier")
    updated = _save({**order, **patch})
    # A confirmed order moving date must move to the right route run.
    if order["status"] == "confirmed" and patch.get("deliveryDate") and patch["deliveryDate"] != order["deliveryDate"]:
        run_id = routing.attach_order(updated)
        rest = {k: v for k, v in updated.items() if k != "routeRunId"}
        updated = crud.orders.put({**rest, "routeRunId": run_id} if run_id else rest)
    what = []
    if patch.get("deliveryDate"):
        what.append(f"livraison le {patch['deliveryDate']}")
    if "note" in patch:
        what.append("note")
    log_event(ctx, "order.updated", "order", id, f"Commande {order['number']} modifiée ({', '.join(what)})")
    return order_detail(id)


@transactional
def add_line(ctx: Ctx, id: str, input: Doc) -> Doc:
    order = crud.orders.require(id)
    _guard(order, ["draft", "confirmed"], "ajouter une ligne à")
    line = _build_line(order["clientId"], input)
    _save({**order, "lines": [*order["lines"], line]})
    p = crud.products.require(line["productId"])
    log_event(ctx, "order.line_added", "order", id, f"{js_str(line['qty'])} {p['unit']} de {p['name']} ajouté(s) à {order['number']}")
    return order_detail(id)


@transactional
def update_line(ctx: Ctx, id: str, line_id: str, patch: Doc) -> Doc:
    order = crud.orders.require(id)
    line = next((l for l in order["lines"] if l["id"] == line_id), None)
    if not line:
        raise bad_request("unknown_line", f"Ligne {line_id} introuvable sur {order['number']}")
    # Once picked, only the prepared quantity and the note can change.
    only_prep = all(k in ("preparedQty", "note") for k in patch)
    _guard(order, ["draft", "confirmed", "prepared"] if only_prep else ["draft", "confirmed"], "modifier une ligne de")
    updated = {**line, **patch}
    if patch.get("productId") and patch["productId"] != line["productId"]:
        rebuilt = _build_line(order["clientId"], {"productId": patch["productId"], "qty": patch.get("qty", line["qty"]), "unitPrice": patch.get("unitPrice")})
        updated = {**updated, "productId": rebuilt["productId"], "unitPrice": rebuilt["unitPrice"]}
    if not updated["qty"] > 0:
        raise bad_request("invalid_qty", "La quantité doit être positive")
    if updated.get("preparedQty") is not None and updated["preparedQty"] < 0:
        raise bad_request("invalid_qty", "Quantité préparée négative")
    updated["unitPrice"] = round2(updated["unitPrice"])
    _save({**order, "lines": [updated if l["id"] == line_id else l for l in order["lines"]]})
    p = crud.products.get(updated["productId"])
    log_event(ctx, "order.line_updated", "order", id, f"Ligne {p['name'] if p else updated['productId']} modifiée sur {order['number']}")
    return order_detail(id)


@transactional
def delete_line(ctx: Ctx, id: str, line_id: str) -> Doc:
    order = crud.orders.require(id)
    _guard(order, ["draft", "confirmed"], "retirer une ligne de")
    line = next((l for l in order["lines"] if l["id"] == line_id), None)
    if not line:
        raise bad_request("unknown_line", f"Ligne {line_id} introuvable sur {order['number']}")
    if order["status"] == "confirmed" and len(order["lines"]) == 1:
        raise conflict("empty_order", f"Impossible de retirer la dernière ligne de {order['number']} confirmée : annulez la commande")
    _save({**order, "lines": [l for l in order["lines"] if l["id"] != line_id]})
    p = crud.products.get(line["productId"])
    log_event(ctx, "order.line_removed", "order", id, f"{p['name'] if p else line['productId']} retiré de {order['number']}")
    return order_detail(id)


@transactional
def confirm_order(ctx: Ctx, id: str) -> Doc:
    """draft → confirmed. Warnings never block; they are returned on the detail."""
    order = crud.orders.require(id)
    _guard(order, ["draft"], "confirmer")
    if not order["lines"]:
        raise conflict("empty_order", f"La commande {order['number']} n'a aucune ligne")
    confirmed = _save({**order, "status": "confirmed", "confirmedAt": now()})
    run_id = routing.attach_order(confirmed)
    if run_id:
        crud.orders.put({**confirmed, "routeRunId": run_id})
    detail = order_detail(id)
    warn = f" — {len(detail['warnings'])} alerte(s)" if detail["warnings"] else ""
    log_event(ctx, "order.confirmed", "order", id,
              f"Commande {order['number']} confirmée pour {detail['client']['name']} ({fmt_eur(detail['totalHt'])} HT){warn}")  # fmt: skip
    return detail


@transactional
def prepare_order(ctx: Ctx, id: str, prepared: list[Doc] | None = None) -> Doc:
    """confirmed → prepared. Lines not listed are considered picked exactly as ordered."""
    order = crud.orders.require(id)
    _guard(order, ["confirmed"], "préparer")
    by_line = {p["lineId"]: p["preparedQty"] for p in prepared or []}
    for line_id in by_line:
        if not any(l["id"] == line_id for l in order["lines"]):
            raise bad_request("unknown_line", f"Ligne {line_id} introuvable sur {order['number']}")
    lines = [{**l, "preparedQty": by_line.get(l["id"], line_qty(l))} for l in order["lines"]]
    _save({**order, "lines": lines, "status": "prepared"})
    log_event(ctx, "order.prepared", "order", id, f"Commande {order['number']} préparée ({fmt_eur(_total_ht(lines))} HT)")
    return order_detail(id)


@transactional
def deliver_order(ctx: Ctx, id: str) -> Doc:
    """confirmed|prepared → delivered: stock leaves the warehouse, FEFO."""
    order = crud.orders.require(id)
    _guard(order, ["confirmed", "prepared"], "livrer")
    lines = [{**l, "preparedQty": line_qty(l)} for l in order["lines"]]
    shortages = []
    for l in lines:
        missing = consume_fefo(l["productId"], l["preparedQty"], "sale", {"refType": "order", "refId": order["id"]})
        if missing > 0:
            p = crud.products.get(l["productId"])
            shortages.append(f"{p['name'] if p else l['productId']} ({js_str(missing)} manquant)")
    delivered = _save({**order, "lines": lines, "status": "delivered", "deliveredAt": now()})
    routing.mark_stop_delivered(delivered)
    client = crud.clients.get(order["clientId"])
    extra = f" — stock physique insuffisant : {', '.join(shortages)}" if shortages else ""
    log_event(ctx, "order.delivered", "order", id, f"Commande {order['number']} livrée à {client['name'] if client else '?'}{extra}")
    return order_detail(id)


@transactional
def invoice_from_order(ctx: Ctx, id: str) -> Doc:
    """delivered → invoiced. Returns the invoice detail."""
    order = crud.orders.require(id)
    inv = invoices.invoice_order(ctx, order)
    return invoices.invoice_detail(inv["id"])


@transactional
def cancel_order(ctx: Ctx, id: str) -> Doc:
    """draft|confirmed|prepared → cancelled. The reservation disappears with the status; the stop leaves its run."""
    order = crud.orders.require(id)
    _guard(order, ["draft", "confirmed", "prepared"], "annuler")
    cancelled = _save({**order, "status": "cancelled"})
    routing.detach_order(cancelled)
    crud.orders.put({k: v for k, v in cancelled.items() if k != "routeRunId"})
    log_event(ctx, "order.cancelled", "order", id, f"Commande {order['number']} annulée")
    return order_detail(id)
