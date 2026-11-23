"""
THE wire contract of the AI service (HTTP bodies, SSE events, WS messages), as Pydantic models.

JSON is camelCase; Python attributes are snake_case. Everything here is published in /openapi.json
(the event and message unions too), so the web app's TypeScript types can be generated from it.
"""

from .chat import (
    ChatMessage,
    ChatMode,
    ChatRequest,
    ChatStreamEvent,
    DoneEvent,
    ErrorEvent,
    TextEvent,
    ToolCall,
    ToolCallEvent,
    ToolInfo,
    ToolResultEvent,
    TurnTimings,
    Usage,
)
from .command import CommandRequest, CommandStreamEvent, NavigateEvent, SpeechEvent, TranscriptEvent
from .service import MOCK_TTS_MIME, ErrorResponse, HealthResponse, LLMInfo, ProviderInfo, SttResponse, TtsRequest
from .voice import (
    AgentAudioEndMessage,
    AgentAudioStartMessage,
    AgentDoneMessage,
    AgentTextMessage,
    AgentToolMessage,
    AudioEndMessage,
    AudioStartMessage,
    ReadyMessage,
    ResetMessage,
    StartMessage,
    TextMessage,
    TranscriptMessage,
    VoiceClientMessage,
    VoiceErrorMessage,
    VoiceServerMessage,
)

__all__ = [name for name in dir() if not name.startswith("_")]
