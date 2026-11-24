"""The outbound demo only controls the simulated browser and its local SMS outbox."""

import os
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends

from app.core.errors import not_found, validation_error
from app.schemas.base import Input, Schema
from app.services import outbound_calls
from .recommendations import Offer, enabled as recommendations_enabled

router = APIRouter(prefix="/api/outbound-demo", tags=["outbound-demo"])


def enabled() -> bool:
    return recommendations_enabled() and os.environ.get("TEAM_OUTBOUND_DEMO", "").strip().lower() in {"1", "true", "yes", "on"}


def require_enabled() -> None:
    if not enabled():
        raise not_found("Fonctionnalité", "appels sortants")


class Target(Schema):
    client_id: str
    client_name: str
    offer: Offer


class Attempt(Target):
    id: str
    status: Literal["ringing", "answered", "missed", "completed", "cancelled"]
    started_at: float
    deadline: float
    sms: str | None = None
    reason: str | None = None


class AnsweredAttempt(Attempt):
    session_id: str | None = None


class Start(Input):
    request_id: str


class Session(Input):
    session_id: str


@router.get("/status")
async def outbound_demo_status():
    return {"enabled": enabled()}


@router.get("/candidates", response_model=list[Target], dependencies=[Depends(require_enabled)])
async def outbound_demo_candidates():
    return outbound_calls.candidates()[:10]


@router.get("/attempts", response_model=list[Attempt], dependencies=[Depends(require_enabled)])
async def outbound_demo_attempts():
    return outbound_calls.list_attempts()


@router.post("/attempts", response_model=Attempt, dependencies=[Depends(require_enabled)])
async def start_outbound_demo(body: Start):
    try:
        request_id = str(UUID(body.request_id))
    except ValueError:
        raise validation_error("requestId : UUID attendu") from None
    return outbound_calls.start(request_id)


@router.post("/attempts/{attempt_id}/answer", response_model=AnsweredAttempt, dependencies=[Depends(require_enabled)])
async def answer_outbound_demo(attempt_id: str, body: Session):
    return outbound_calls.answer(attempt_id, body.session_id)


@router.post("/attempts/{attempt_id}/complete", dependencies=[Depends(require_enabled)])
async def complete_outbound_demo(attempt_id: str, body: Session):
    outbound_calls.complete(attempt_id, body.session_id)
    return {"ok": True}


@router.post("/attempts/{attempt_id}/dismiss", dependencies=[Depends(require_enabled)])
async def dismiss_outbound_demo(attempt_id: str):
    outbound_calls.dismiss(attempt_id)
    return {"ok": True}
