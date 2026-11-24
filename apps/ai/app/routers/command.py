"""POST /command[?speak=1]: one voice command (raw audio or JSON {text}) → SSE of CommandStreamEvent."""

import re
from urllib.parse import unquote

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.schemas import CommandRequest, ErrorResponse
from app.services.command import run_command

from .sse import sse_doc, sse_response

router = APIRouter(tags=["agent"])

REQUEST_BODY = {
    "required": True,
    "content": {
        "application/json": {"schema": {"$ref": "#/components/schemas/CommandRequest"}},
        "audio/*": {"schema": {"type": "string", "format": "binary"}},
    },
}


@router.post("/command", responses=sse_doc("CommandStreamEvent"), openapi_extra={"requestBody": REQUEST_BODY})
async def command(request: Request, speak: str | None = None):
    """
    Single-turn voice COMMAND, stateless and act-first. Body: raw audio (content-type = its mime; header
    x-mock-text for the mock STT) or JSON CommandRequest. `speak=1` adds a `speech` event (base64 TTS).
    """
    content_type = request.headers.get("content-type", "")
    typed: CommandRequest | None = None
    audio: bytes | None = None
    if "application/json" in content_type:
        try:
            typed = CommandRequest.model_validate_json(await request.body())
        except ValidationError:
            typed = None
        if not typed or not typed.text.strip():
            return JSONResponse(ErrorResponse.of("bad_request", "text required (or send raw audio)"), status_code=400)
    else:
        audio = await request.body()
        if not audio:
            return JSONResponse(ErrorResponse.of("bad_request", "empty audio body"), status_code=400)

    return sse_response(
        run_command(
            text=typed.text if typed else None,
            audio=audio,
            mime=content_type or "audio/webm",
            hint=header_text(request.headers.get("x-mock-text") or request.headers.get("x-stt-hint")),
            actor_name=(typed and typed.actor_name) or header_text(request.headers.get("x-actor-name")) or "Commande vocale",
            speak=speak in ("1", "true"),
        )
    )


def header_text(value: str | None) -> str | None:
    """Header values are latin-1 on the wire: accept percent-encoded text (browsers) or raw UTF-8 bytes (curl)."""
    if not value:
        return value
    if re.search(r"%[0-9A-F]{2}", value, re.I):
        try:
            return unquote(value, errors="strict")
        except UnicodeDecodeError:
            pass  # not encoded after all
    if re.search(r"[\x80-\xff]", value):
        return value.encode("latin-1").decode("utf-8", "replace")
    return value
