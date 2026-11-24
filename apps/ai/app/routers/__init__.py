"""HTTP / WebSocket routes. Thin: parse the request, call the agent or a service, stream the result."""

from . import chat, command, health, outbound, speech, voice

routers = [health.router, chat.router, command.router, speech.router, voice.router, outbound.router]  # outbound: team 12 (Youssef), Lucie's voice message
