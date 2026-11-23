"""HTTP / WebSocket routes. Thin: parse the request, call the agent or a service, stream the result."""

from . import chat, command, health, speech, voice

routers = [health.router, chat.router, command.router, speech.router, voice.router]
