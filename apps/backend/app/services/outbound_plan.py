"""
Team 12 (Youssef) · Lucie plans her own outbound calls (TEAM_OUTBOUND_DEMO, on top of Mohamed Amine's simulated calls).

For each reachable client with a verified offer (recommendations.select, through outbound_calls.candidates): who, why
(what they buy, the offer), and when: 30 min before the hour they usually order (their past orders), so the call lands
before they place it, else the next free slot. The page starts a planned call by itself when its time comes (if the
page is open), or at once with « Appeler maintenant ». Deterministic: no model, nothing invented.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import date, datetime
from statistics import median
from zoneinfo import ZoneInfo

from app import crud
from app.core.db import Doc
from app.core.errors import not_found
from app.services import outbound_calls

PARIS = ZoneInfo("Europe/Paris")
MAX_CALLS = 4
GAP_MIN, LEAD_MIN = 5, 30  # calls ≥ 5 min apart, 30 min before the usual order


def first_slot_min() -> int:
    """Minutes before the first call (TEAM_OUTBOUND_FIRST_CALL_MIN, default 3; 1 for a quick demo)."""
    try:
        return max(1, int(os.environ.get("TEAM_OUTBOUND_FIRST_CALL_MIN", "3")))
    except ValueError:
        return 3
MONTHS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"]
PLAN: dict[str, Doc] = {}  # id → planned call (also the id of its attempt once started)


def usual_order_minute(client_id: str) -> int | None:
    """The minute of the day the client usually orders (median of its orders' times), or None."""
    minutes = []
    for o in crud.orders.rows.values():
        at = o.get("createdAt") or ""
        if o.get("clientId") == client_id and len(at) >= 16:
            minutes.append(int(at[11:13]) * 60 + int(at[14:16]))
    return round(median(minutes) / 15) * 15 if len(minutes) >= 2 else None  # « vers 13 h 30 », not 13 h 32


def _hhmm(minute: int) -> str:
    return f"{minute // 60} h {minute % 60:02d}" if minute % 60 else f"{minute // 60} h"


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} {MONTHS[d.month - 1]}"


def reasons(target: Doc, contact: str | None) -> list[str]:
    offer = target["offer"]
    product = offer["productName"].split(" (")[0]
    product = product[:1].lower() + product[1:]
    out = []
    if offer.get("purchaseCount"):
        last = f", dernier achat le {_day(offer['lastPurchasedOn'])}" if offer.get("lastPurchasedOn") else ""
        out.append(f"Achète le {product} régulièrement ({offer['purchaseCount']} fois récemment{last})")
    if offer["kind"] == "promo" and offer.get("validUntil"):
        out.append(f"En promo à {offer['unitPrice']:.2f} € HT jusqu'au {_day(offer['validUntil'])}".replace(".", ","))
    elif offer["kind"] == "new":
        out.append("Nouveauté qui correspond à sa gamme habituelle")
    if contact:
        out.append(f"Interlocuteur : {contact}")
    return out


def build(now: float | None = None) -> list[Doc]:
    """A fresh plan: the best offer per client (candidates are already ranked), at most MAX_CALLS clients."""
    now = now or time.time()
    local = datetime.fromtimestamp(now, PARIS)
    now_min, first = local.hour * 60 + local.minute, first_slot_min()
    taken: list[int] = []
    PLAN.clear()
    seen: set[str] = set()
    for target in outbound_calls.candidates():
        if target["clientId"] in seen or len(seen) >= MAX_CALLS:
            continue
        seen.add(target["clientId"])
        client = crud.clients.require(target["clientId"])
        contact = next((c.get("name") for c in client.get("contacts") or [] if c.get("phone")), None)
        usual = usual_order_minute(target["clientId"])
        wished = usual - LEAD_MIN if usual is not None else None
        slot = wished if wished is not None and wished >= now_min + first else now_min + first
        while any(abs(slot - t) < GAP_MIN for t in taken):
            slot += GAP_MIN
        taken.append(slot)
        if wished is not None and slot == wished:
            why = f"Il commande d'habitude vers {_hhmm(usual)} : Lucie l'appelle juste avant, à {_hhmm(slot)}."
        elif usual is not None:
            why = f"Il commande d'habitude vers {_hhmm(usual)}, déjà passé aujourd'hui : prochain créneau libre, {_hhmm(slot)}."
        else:
            why = f"Pas d'heure habituelle connue : prochain créneau libre, {_hhmm(slot)}."
        at = local.replace(hour=0, minute=0, second=0, microsecond=0).timestamp() + slot * 60
        pid = str(uuid.uuid4())
        PLAN[pid] = {
            "id": pid, "clientId": target["clientId"], "clientName": target["clientName"], "contact": contact,
            "offer": target["offer"], "reasons": reasons(target, contact), "whyTime": why, "at": at,
        }  # fmt: skip
    return listing()


def listing() -> list[Doc]:
    """The plan with each call's live status (planned until its attempt starts, then the attempt's status)."""
    out = []
    for entry in PLAN.values():
        attempt = crud.outbound_attempts.get(entry["id"])
        out.append({**entry, "status": attempt["status"] if attempt else "planned"})
    return sorted(out, key=lambda e: e["at"])


def current() -> list[Doc]:
    """The plan, made on first use and again once every call of it is over."""
    if not PLAN or all(e["status"] in {"missed", "completed", "cancelled"} for e in listing()):
        return build()
    return listing()


def call_now(plan_id: str) -> Doc:
    entry = PLAN.get(plan_id)
    if not entry:
        raise not_found("Appel planifié", plan_id)
    return outbound_calls.start(plan_id, client_id=entry["clientId"], offer_id=entry["offer"]["id"])


def decline(plan_id: str) -> Doc:
    """The call is refused while it rings: it ends now as unanswered (then Lucie leaves her voice message)."""
    attempt = crud.outbound_attempts.get(plan_id)
    if not attempt:
        raise not_found("Appel", plan_id)
    if attempt["status"] == "ringing":
        attempt = crud.outbound_attempts.put({**attempt, "deadline": time.time()})  # process_due marks it missed
    return attempt
