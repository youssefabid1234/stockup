"""Delivery routes (tournées). A Route serves one zone on some weekdays; a RouteRun is that route
on one date. Orders are attached to the run of their client's zone on their delivery date.
ETAs = departure time + 12 min per stop."""

from __future__ import annotations

from app import crud
from app.core.activity import Ctx, log_event
from app.core.listing import ListQuery, respond
from app.core.db import Doc, transactional
from app.core.errors import bad_request
from app.core.utils import add_minutes, locale_cmp, round2, sort_by, total, weekday_of
from app.services.stock import line_qty

MINUTES_PER_STOP = 12


def route_for(zone: str, date: str) -> Doc | None:
    """Route serving this zone on this date: prefer one running that weekday, else any route of the zone."""
    routes = crud.routes.filter(lambda r: r["zone"] == zone)
    day = weekday_of(date)
    return next((r for r in routes if day in r["days"]), routes[0] if routes else None)


def zone_served_on(zone: str, date: str) -> bool:
    """True when a route of the zone actually runs that weekday."""
    day = weekday_of(date)
    return any(r["zone"] == zone and day in r["days"] for r in crud.routes.all())


def weight_kg(product: Doc | None, qty: float) -> float:
    """Approximate weight: kg/liter as-is, a box ≈ 5 kg, a piece or a dozen ≈ 1 kg."""
    unit = product["unit"] if product else None
    return qty * 5 if unit == "box" else qty


def _order_weight(order: Doc) -> float:
    return round2(total(weight_kg(crud.products.get(l["productId"]), line_qty(l)) for l in order["lines"]))


def _resequence(stops: list[Doc], route: Doc) -> list[Doc]:
    """Renumber stops 1..n and recompute ETAs from the route departure time."""
    return [
        {**s, "seq": i + 1, "eta": add_minutes(route["departureTime"], MINUTES_PER_STOP * (i + 1))}
        for i, s in enumerate(stops)
    ]


def _get_or_create_run(route: Doc, date: str) -> Doc:
    for run in crud.route_runs.all():
        if run["routeId"] == route["id"] and run["date"] == date:
            return run
    return crud.route_runs.put({"id": crud.route_runs.next_id("run_"), "routeId": route["id"], "date": date, "status": "planned", "stops": []})


def attach_order(order: Doc) -> str | None:
    """Put an order on its run (creating the run if needed). Returns the run id, or None if no route serves the zone."""
    client = crud.clients.require(order["clientId"])
    route = route_for(client["zone"], order["deliveryDate"])
    if not route:
        return None
    detach_order(order)  # the date may have changed
    run = _get_or_create_run(route, order["deliveryDate"])
    stops = [*run["stops"], {"orderId": order["id"], "clientId": client["id"], "seq": 0, "status": "pending"}]
    crud.route_runs.put({**run, "stops": _resequence(stops, route)})
    return run["id"]


def detach_order(order: Doc) -> None:
    """Remove an order from whatever run holds it (cancel, date change)."""
    for run in crud.route_runs.all():
        if not any(s["orderId"] == order["id"] for s in run["stops"]):
            continue
        route = crud.routes.require(run["routeId"])
        stops = [s for s in run["stops"] if s["orderId"] != order["id"]]
        crud.route_runs.put({**run, "stops": _resequence(stops, route)})


def mark_stop_delivered(order: Doc) -> None:
    """Mark the stop of a delivered order; the run becomes in_progress, then done when no stop is pending."""
    for run in crud.route_runs.all():
        if not any(s["orderId"] == order["id"] for s in run["stops"]):
            continue
        stops = [{**s, "status": "delivered"} if s["orderId"] == order["id"] else s for s in run["stops"]]
        status = "done" if all(s["status"] != "pending" for s in stops) else "in_progress"
        crud.route_runs.put({**run, "stops": stops, "status": status})


def route_run_detail(run: Doc) -> Doc:
    route = crud.routes.require(run["routeId"])
    stops = []
    for s in run["stops"]:
        client = crud.clients.get(s["clientId"]) or {}
        order = crud.orders.get(s["orderId"])
        stops.append({
            **s,
            "clientName": client.get("name", "?"),
            "address": client.get("address", ""),
            "city": client.get("city", ""),
            "orderNumber": order["number"] if order else "?",
            "weightKg": _order_weight(order) if order else 0,
        })  # fmt: skip
    return {**run, "route": route, "stops": stops, "totalWeightKg": round2(total(s["weightKg"] for s in stops))}


def list_route_runs(date: str | None = None, lq: ListQuery | None = None, route_id: str | None = None) -> list[Doc] | Doc:
    """Newest date first, then by route. Details (stops with client + order) are built for the page only."""
    runs = crud.route_runs.filter(lambda r: (not date or r["date"] == date) and (not route_id or r["routeId"] == route_id))
    runs.sort(key=lambda r: r["routeId"])
    runs.sort(key=lambda r: r["date"], reverse=True)
    return respond(runs, lq or ListQuery(limit=10**9), route_run_detail)


@transactional
def plan_day(ctx: Ctx, date: str) -> list[Doc]:
    """Plan a day: every confirmed/prepared order of `date` goes on the run of its client's zone.
    Existing stop order is kept; new orders are appended grouped by city then client name.
    Orders of a zone without any route are left unplanned."""

    def by_city_then_name(a: Doc, b: Doc) -> int:
        ca, cb = crud.clients.require(a["clientId"]), crud.clients.require(b["clientId"])
        return locale_cmp(ca["city"], cb["city"]) or locale_cmp(ca["name"], cb["name"])

    orders = crud.orders.filter(lambda o: o["deliveryDate"] == date and o["status"] in ("confirmed", "prepared"))
    orders = sort_by(orders, by_city_then_name)

    touched: list[str] = []
    planned = 0
    for order in orders:
        client = crud.clients.require(order["clientId"])
        route = route_for(client["zone"], date)
        if not route:
            continue
        run = _get_or_create_run(route, date)
        if run["id"] not in touched:
            touched.append(run["id"])
        if any(s["orderId"] == order["id"] for s in run["stops"]):
            if order.get("routeRunId") != run["id"]:
                crud.orders.put({**order, "routeRunId": run["id"]})
            continue
        detach_order(order)
        fresh = crud.route_runs.require(run["id"])
        stops = [*fresh["stops"], {"orderId": order["id"], "clientId": client["id"], "seq": 0, "status": "pending"}]
        crud.route_runs.put({**fresh, "stops": _resequence(stops, route)})
        crud.orders.put({**order, "routeRunId": run["id"]})
        planned += 1

    # Drop stops whose order was cancelled or moved to another date.
    for run_id in touched:
        run = crud.route_runs.require(run_id)

        def still_here(s: Doc) -> bool:
            o = crud.orders.get(s["orderId"])
            return bool(o) and o["status"] not in ("cancelled", "draft") and o["deliveryDate"] == date

        stops = [s for s in run["stops"] if still_here(s)]
        if len(stops) != len(run["stops"]):
            crud.route_runs.put({**run, "stops": _resequence(stops, crud.routes.require(run["routeId"]))})

    log_event(ctx, "route_run.planned", "route_run", date,
              f"Tournées du {date} planifiées : {len(touched)} tournée(s), {planned} nouvel(s) arrêt(s)")  # fmt: skip
    return list_route_runs(date)


@transactional
def reorder_stops(ctx: Ctx, run_id: str, order_ids: list[str]) -> Doc:
    """Given order ids first in that order; any stop not listed keeps its relative order after them."""
    run = crud.route_runs.require(run_id)
    route = crud.routes.require(run["routeId"])
    by_order = {s["orderId"]: s for s in run["stops"]}
    for oid in order_ids:
        if oid not in by_order:
            raise bad_request("unknown_stop", f"La commande {oid} n'est pas sur cette tournée")
    listed = [by_order[oid] for oid in order_ids]
    rest = [s for s in run["stops"] if s["orderId"] not in order_ids]
    updated = crud.route_runs.put({**run, "stops": _resequence([*listed, *rest], route)})
    log_event(ctx, "route_run.reordered", "route_run", run["id"], f"Ordre des arrêts modifié sur {route['name']} du {run['date']}")
    return route_run_detail(updated)
