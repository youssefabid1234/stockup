"""WS /voice: push-to-talk voice sessions (protocol: app/schemas/voice.py, logic: app/services/voice_session.py).
WS /voice/command: one voice command with live transcription (app/services/command.py, serve_command_ws)."""

from fastapi import APIRouter, WebSocket

from app.services.command import serve_command_ws
from app.services.voice_session import VoiceConnection

router = APIRouter()


@router.websocket("/voice")
async def voice(ws: WebSocket):
    await VoiceConnection(ws).serve()


@router.websocket("/voice/command")
async def voice_command(ws: WebSocket, speak: str | None = None):
    await serve_command_ws(ws, speak=speak in ("1", "true"))
