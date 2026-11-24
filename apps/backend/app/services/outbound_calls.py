"""Persistent state and CRM records for the simulated outbound phone and SMS channels."""

import asyncio
import logging
import os
import time
from datetime import date

from app import crud
from app.core.activity import Ctx
from app.core.db import Doc, get_meta, transactional
from app.core.errors import conflict
from app.services import client_events, recommendations

ACTOR = Ctx(actor="voice_agent")
LOG = logging.getLogger(__name__)


def _has_phone(client: Doc) -> bool:
    return any(c.get("phone") for c in client.get("contacts") or [])


def candidates() -> list[Doc]:
    seen = {(a["clientId"], a["offer"]["id"]) for a in crud.outbound_attempts.rows.values()}
    matches = []
    for client in crud.clients.rows.values():
        if not _has_phone(client):
            continue
        for offer in recommendations.select(client["id"], outbound=True):
            if (client["id"], offer["id"]) not in seen:
                matches.append({"clientId": client["id"], "clientName": client["name"], "offer": offer})
    return sorted(matches, key=lambda m: (
        m["offer"]["kind"] != "promo", -m["offer"]["purchaseCount"], m["clientName"], m["offer"]["id"],
    ))


def list_attempts() -> list[Doc]:
    return sorted(crud.outbound_attempts.rows.values(), key=lambda a: a["startedAt"], reverse=True)[:25]


@transactional
def start(request_id: str) -> Doc:
    if previous := crud.outbound_attempts.get(request_id):
        return previous
    if any(a["status"] in {"ringing", "answered"} for a in crud.outbound_attempts.rows.values()):
        raise conflict("call_in_progress", "Un appel sortant est déjà en cours.")
    if not (eligible := candidates()):
        raise conflict("no_offer", "Aucune offre disponible pour un client joignable.")
    now = time.time()
    try:
        seconds = max(1, min(60, int(os.environ.get("TEAM_OUTBOUND_RING_SECONDS", "10"))))
    except ValueError:
        seconds = 10
    attempt = {**eligible[0], "id": request_id, "status": "ringing", "startedAt": now, "deadline": now + seconds}
    return crud.outbound_attempts.put(attempt)


def _log(attempt: Doc, title: str, *, channel: str = "phone", description: str = "") -> None:
    client_events.create_client_event(ACTOR, attempt["clientId"], {
        "type": "call", "channel": channel, "title": title, "description": description,
        "productIds": [attempt["offer"]["productId"]],
    })


def _missed(attempt: Doc) -> Doc:
    fresh = recommendations.fresh_offer(attempt["clientId"], attempt["offer"])
    phone = _has_phone(crud.clients.require(attempt["clientId"]))
    _log(attempt, "Appel sortant simulé sans réponse")
    updated = {**attempt, "status": "missed"}
    if fresh and phone:
        company = get_meta().get("company") or "Le Fournil Occitan"
        product = fresh["productName"]
        if fresh["kind"] == "promo":
            until = date.fromisoformat(fresh["validUntil"]).strftime("%d/%m")
            body = f"Bonjour, ici {company}. {product} est en promotion jusqu’au {until}. Vous pouvez nous rappeler si vous souhaitez en profiter."
        else:
            body = f"Bonjour, ici {company}. {product} vient d’arriver au catalogue. Vous pouvez nous rappeler pour en savoir plus."
        updated.update(sms=body)
        _log(attempt, "SMS de suivi simulé", channel="sms", description=body)
    else:
        updated.update(reason="L’offre ou le contact n’est plus disponible.")
    return crud.outbound_attempts.put(updated)


@transactional
def answer(attempt_id: str, session_id: str) -> Doc:
    attempt = crud.outbound_attempts.require(attempt_id)
    if attempt["status"] == "answered" and attempt.get("sessionId") == session_id:
        return attempt
    if attempt["status"] != "ringing":
        return attempt
    if time.time() >= attempt["deadline"]:
        return _missed(attempt)
    fresh = recommendations.fresh_offer(attempt["clientId"], attempt["offer"])
    if not fresh or not _has_phone(crud.clients.require(attempt["clientId"])):
        return crud.outbound_attempts.put({**attempt, "status": "cancelled", "reason": "L’offre ou le contact n’est plus disponible."})
    _log(attempt, "Appel sortant simulé décroché")
    return crud.outbound_attempts.put({
        **attempt, "status": "answered", "offer": fresh, "sessionId": session_id, "answeredAt": time.time(),
    })


@transactional
def complete(attempt_id: str, session_id: str) -> None:
    attempt = crud.outbound_attempts.get(attempt_id)
    if attempt and attempt["status"] == "answered" and attempt.get("sessionId") == session_id:
        _log(attempt, "Appel sortant simulé terminé")
        crud.outbound_attempts.put({**attempt, "status": "completed"})


@transactional
def _expire_attempt(attempt_id: str, now: float) -> None:
    attempt = crud.outbound_attempts.require(attempt_id)
    if attempt["status"] == "ringing" and now >= attempt["deadline"]:
        _missed(attempt)
    elif attempt["status"] == "answered" and now - attempt["answeredAt"] >= 15 * 60:
        complete(attempt_id, attempt["sessionId"])


async def process_due() -> None:
    while True:
        for attempt_id in list(crud.outbound_attempts.rows):
            attempt = crud.outbound_attempts.get(attempt_id)
            if not attempt or attempt["status"] not in {"ringing", "answered"}:
                continue
            try:
                _expire_attempt(attempt_id, time.time())
            except Exception:
                LOG.exception("Erreur pendant le traitement de l’appel sortant simulé %s", attempt_id)
        await asyncio.sleep(0.5)
