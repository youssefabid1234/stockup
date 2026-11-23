"""
The three interfaces every provider implements. The rest of the service only knows these.

    LLMClient.stream(request)        → async iterator of LLMText / LLMToolCall / LLMUsage
    STTClient.transcribe(audio, …)   → text          (+ transcribe_stream: audio chunks → live STTUpdate)
    TTSClient.synthesize(text, …)    → TTSResult(mime, async iterator of audio bytes)

Interrupting (barge-in, client disconnected) is plain asyncio cancellation: no abort signal to pass around.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

from app.schemas import ChatMessage, ToolCall, ToolInfo

# ── LLM ──


@dataclass
class LLMRequest:
    system: str
    messages: list[ChatMessage]  # user / assistant (with tool_calls) / tool (with tool_call_id + name)
    tools: list[ToolInfo] = field(default_factory=list)
    max_tokens: int | None = None


@dataclass
class LLMText:
    """A piece of the answer: shown / spoken as it arrives."""

    delta: str


@dataclass
class LLMToolCall:
    """The model wants a tool to run. The agent loop executes it and calls the model again."""

    call: ToolCall


@dataclass
class LLMUsage:
    input_tokens: int | None = None  # Anthropic: uncached input only (total = input + cache_creation + cache_read)
    output_tokens: int | None = None
    cache_creation_input_tokens: int | None = None  # prompt cache written (Anthropic), ~1.25x price
    cache_read_input_tokens: int | None = None  # prompt cache hit (Anthropic), ~0.1x price


LLMEvent = LLMText | LLMToolCall | LLMUsage


class LLMClient(ABC):
    provider: str
    model: str

    @abstractmethod
    def stream(self, request: LLMRequest) -> AsyncIterator[LLMEvent]:
        """Stream one model response. Implement it as an `async def` generator (with `yield`)."""


# ── Speech ──


@dataclass
class STTUpdate:
    """Live transcription progress. `text` is the whole transcript so far, provisional words included;
    `stable` is its leading part made of final words only (the provider will not change it any more).
    The last update of a stream has final=True and the definitive text."""

    text: str
    final: bool = False
    stable: str = ""


class STTClient(ABC):
    name: str
    # True when transcribe_stream() really transcribes while the audio arrives (real-time WebSocket):
    # the voice session then streams push-to-talk audio as it is recorded and shows partial transcripts.
    streams: bool = False

    @abstractmethod
    async def transcribe(self, audio: bytes, mime: str, hint: str | None = None) -> str:
        """Whole utterance in, text out (the fallback when live transcription is not available or broke).
        `hint`: vocabulary (client / product names, comma-separated) to help the model; the mock returns it as the transcript.
        `mime`: what the browser recorded, usually "audio/webm;codecs=opus" (Safari: "audio/mp4")."""

    async def transcribe_stream(self, audio: AsyncIterator[bytes], mime: str, hint: str | None = None) -> AsyncIterator[STTUpdate]:
        """Live transcription: audio chunks in (MediaRecorder frames while the key is down), STTUpdate out as
        words are recognised, ending with one final=True update soon after the audio ends.
        Used by services/utterance.py when `streams` is True.

        Default: waits for the end of the audio, then one final update from transcribe(). Soniox and Deepgram
        override it with their real-time WebSockets (and set streams = True)."""
        text = await self.transcribe(b"".join([chunk async for chunk in audio]), mime, hint)
        yield STTUpdate(text, final=True, stable=text)


@dataclass
class TTSResult:
    mime: str  # "audio/mpeg" for every real provider (the web player streams mp3), MOCK_TTS_MIME for the mock
    chunks: AsyncIterator[bytes]  # bytes as they arrive (first byte early = low latency)


class TTSClient(ABC):
    name: str

    @abstractmethod
    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
        """Start synthesis; raise on HTTP errors, then stream the audio through `TTSResult.chunks`."""
