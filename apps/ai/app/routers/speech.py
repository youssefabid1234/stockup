"""POST /stt and POST /tts: the speech providers on their own (handy to test them)."""

import time
from contextlib import aclosing

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.agent.loop import ms_since
from app.clients import get_stt_client, get_tts_client
from app.schemas import ErrorResponse, SttResponse, TtsRequest

router = APIRouter(tags=["speech"])

AUDIO_BODY = {"required": True, "content": {"audio/*": {"schema": {"type": "string", "format": "binary"}}}}


@router.post(
    "/stt",
    response_model=SttResponse,
    responses={502: {"model": ErrorResponse}},
    openapi_extra={"requestBody": AUDIO_BODY},
)
async def stt(request: Request):
    """Raw audio body (content-type = its mime) → {text, ms}. Header x-stt-hint (or x-mock-text): vocabulary hint."""
    audio = await request.body()
    mime = request.headers.get("content-type") or "audio/webm"
    hint = request.headers.get("x-mock-text") or request.headers.get("x-stt-hint")
    started = time.perf_counter()
    try:
        text = await get_stt_client().transcribe(audio, mime, hint)
    except Exception as e:
        return JSONResponse(ErrorResponse.of("stt_failed", str(e)), status_code=502)
    return SttResponse(text=text, ms=ms_since(started))


@router.post(
    "/tts",
    response_class=StreamingResponse,
    responses={
        200: {"description": "Audio bytes, streamed. Header x-ms = time to first byte.", "content": {"audio/mpeg": {}}},
        502: {"model": ErrorResponse},
    },
)
async def tts(body: TtsRequest):
    """{text, voice?} → audio bytes, streamed (audio/mpeg, or MOCK_TTS_MIME for the mock)."""
    started = time.perf_counter()
    try:
        result = await get_tts_client().synthesize(body.text, body.voice)
        first = await anext(result.chunks, b"")  # wait for the first byte so x-ms is meaningful
    except Exception as e:
        return JSONResponse(ErrorResponse.of("tts_failed", str(e)), status_code=502)

    async def audio():
        async with aclosing(result.chunks) as chunks:  # type: ignore[type-var]  # client gone → provider stream closed
            yield first
            async for chunk in chunks:
                yield chunk

    return StreamingResponse(audio(), media_type=result.mime, headers={"x-ms": str(ms_since(started))})
