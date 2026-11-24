"""
OWNER: Amine Khalil (idée 2) · switch TEAM_ORDER_RULES (registered only when on)

« À quelle heure vous passez ? » — the time the truck comes, from the ERP's delivery rounds:
  - the client's order for that day is on a planned round → its stop: rank, ETA (departure + 12 min × rank), driver,
    and whether it is already delivered;
  - the round is not planned yet (rounds are planned the day before) → the client's usual time, the median ETA of its
    last deliveries on that round, said as « en général vers … », never as a promise.
"""

import asyncio  # no `from __future__ import annotations`: the tool registry needs the real types
import statistics
from datetime import date

from pydantic import Field

from .erp import enc
from .registry import ToolContext, tool

GONE = ("confirmed", "prepared", "delivered", "invoiced")


def _minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def say_time(minutes: float) -> str:
    """427 → « 7 h 05 », rounded to 5 minutes for a usual time."""
    m = int(round(minutes))
    return f"{m // 60} h {m % 60:02d}"


def _items(rows):
    return rows.get("items", rows) if isinstance(rows, dict) else rows


async def _stop_on(ctx: ToolContext, client_id: str, day: str) -> tuple[dict, dict] | None:
    """(run, stop) of this client on that day, if a round is planned with it."""
    runs = _items(await ctx.erp.get("/api/route-runs", {"date": day}))
    for run in runs:
        for stop in run.get("stops") or []:
            if stop.get("clientId") == client_id:
                return run, stop
    return None


@tool
async def delivery_eta(
    ctx: ToolContext,
    client_id: str,
    delivery_day: str | None = Field(None, description="Le jour tel que dit (« jeudi », « demain ») ; vide = la prochaine livraison"),
) -> dict:
    """
    À quelle heure passe le camion chez ce client : heure prévue sur la tournée si elle est planifiée (rang, chauffeur,
    déjà livré ou non), sinon l'heure habituelle du client (médiane de ses dernières livraisons). Réponds avec « say ».
    """
    from app.agent.rules_order import french_day, next_delivery_date

    from .delivery import pack_now

    meta, client, orders = await asyncio.gather(
        ctx.erp.get("/api/meta"), ctx.erp.get(f"/api/clients/{enc(client_id)}"),
        ctx.erp.get("/api/orders", {"clientId": client_id, "limit": 30}),
    )
    today, hour = pack_now(meta)
    orders = _items(orders)
    if delivery_day:
        d = next_delivery_date(today, client.get("deliveryDays") or [], delivery_day, hour) or today
    else:
        upcoming = sorted(o["deliveryDate"] for o in orders if o.get("status") in GONE + ("draft",)
                          and o.get("deliveryDate", "") >= today.isoformat())
        d = date.fromisoformat(upcoming[0]) if upcoming else (next_delivery_date(today, client.get("deliveryDays") or [], None, hour) or today)
    day = d.isoformat()

    found = await _stop_on(ctx, client_id, day)
    if found:
        run, stop = found
        route = run.get("route") or {}
        if stop.get("status") == "delivered":
            return {"planned": True, "delivered": True, "say": f"c'est déjà livré, {french_day(d)}"}
        say = (f"{french_day(d)}, le camion de {route.get('driver', 'la tournée').split()[0]} part à "
               f"{say_time(_minutes(route.get('departureTime', '06:30')))} ; vous êtes l'arrêt numéro {stop.get('seq')}, "
               f"arrivée prévue vers {say_time(_minutes(stop['eta']))}")
        return {"planned": True, "eta": stop["eta"], "seq": stop.get("seq"), "say": say}

    # not planned yet: the client's usual time on its last deliveries
    past = sorted({o["deliveryDate"] for o in orders if o.get("status") in ("delivered", "invoiced")}, reverse=True)[:4]
    stops = await asyncio.gather(*(_stop_on(ctx, client_id, p) for p in past))
    etas = [_minutes(s[1]["eta"]) for s in stops if s and s[1].get("eta")]
    if not etas:
        return {"planned": False, "say": f"la tournée de {french_day(d)} n'est pas encore planifiée : l'heure est fixée la veille"}
    usual = round(statistics.median(etas) / 5) * 5
    return {"planned": False, "usualEta": say_time(usual),
            "say": f"{french_day(d)}, en général vers {say_time(usual)} ; l'heure exacte est fixée la veille au soir"}
