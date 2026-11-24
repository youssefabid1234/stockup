"""
Team 12 (Youssef) · POST /outbound/voicemail/{attemptId}: Lucie's voice message after an unanswered outbound call
(text written in her style + her voice), recorded in the client's history; GET …/{attemptId}.mp3 plays it.
Idempotent: the same attempt always gives the same message (the page may ask twice).
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter
from fastapi.responses import JSONResponse, Response

from app.clients import get_tts_client
from app.schemas import ErrorResponse
from app.services.outbound_message import compose, facts_of
from app.tools.erp import ErpClient, enc

router = APIRouter(prefix="/outbound", tags=["outbound"])
MESSAGES: dict[str, dict] = {}
AUDIO: dict[str, tuple[str, bytes]] = {}
_locks: dict[str, asyncio.Lock] = {}


@router.post("/voicemail/{attempt_id}")
async def leave_voicemail(attempt_id: str):
    async with _locks.setdefault(attempt_id, asyncio.Lock()):
        if attempt_id in MESSAGES:
            return MESSAGES[attempt_id]
        erp = ErpClient("voice_agent", "Lucie")
        attempts = await erp.get("/api/outbound-demo/attempts")
        attempt = next((a for a in attempts if a.get("id") == attempt_id), None)
        if not attempt or attempt.get("status") != "missed":
            return JSONResponse(ErrorResponse.of("not_missed", "Pas d'appel manqué pour ce message."), status_code=409)
        client = await erp.get(f"/api/clients/{enc(attempt['clientId'])}")
        contact = next((c for c in client.get("contacts") or [] if c.get("phone")), {})
        text, source = await compose(facts_of(attempt, contact.get("name")))
        started = time.perf_counter()
        result = await get_tts_client().synthesize(text)
        audio = b"".join([chunk async for chunk in result.chunks])
        AUDIO[attempt_id] = (result.mime, audio)
        await erp.post(f"/api/clients/{enc(attempt['clientId'])}/events", {
            "type": "call", "channel": "phone", "title": "Message vocal laissé par Lucie (appel sortant sans réponse)",
            "description": text, "productIds": [attempt["offer"]["productId"]],
        })  # fmt: skip
        print(f"[voicemail] {attempt['clientName']} ({source}, voix {int((time.perf_counter() - started) * 1000)} ms) : {text}", flush=True)
        MESSAGES[attempt_id] = {
            "attemptId": attempt_id, "clientId": attempt["clientId"], "clientName": attempt["clientName"],
            "contact": contact.get("name"), "phone": contact.get("phone"), "text": text, "source": source,
            "audioUrl": f"/ai/outbound/voicemail/{attempt_id}.mp3", "sentAt": time.time(),
        }  # fmt: skip
        return MESSAGES[attempt_id]


@router.get("/voicemail/{attempt_id}.mp3")
async def voicemail_audio(attempt_id: str):
    if attempt_id not in AUDIO:
        return JSONResponse(ErrorResponse.of("not_found", "Message vocal introuvable."), status_code=404)
    mime, audio = AUDIO[attempt_id]
    return Response(audio, media_type=mime)
