"""
WS /voice contract: push-to-talk sessions, two tracks (the human "caller" and the agent).

Client → server: JSON messages below, plus binary audio frames between audio_start and audio_end.
Server → client: JSON messages below, plus binary audio frames between agent_audio_start and agent_audio_end.
"""

from typing import Annotated, Any, Literal, Union

from pydantic import Field

from .base import WireModel
from .chat import TurnTimings

# ── Client → server ──


class StartMessage(WireModel):
    """Opens a conversation (same sessionId again = keep the history)."""

    type: Literal["start"] = "start"
    session_id: str | None = None
    actor_name: str | None = None


class AudioStartMessage(WireModel):
    """Caller pressed the talk key; binary frames follow."""

    type: Literal["audio_start"] = "audio_start"
    mime: str
    hint: str | None = None  # optional STT hint (vocabulary; mock STT: the transcript), like x-mock-text on POST /command


class AudioEndMessage(WireModel):
    """Caller released the key: the frames received since audio_start are the utterance (already streamed to the
    STT as they arrived: send them every 100–250 ms, e.g. MediaRecorder.start(100))."""

    type: Literal["audio_end"] = "audio_end"


class TextMessage(WireModel):
    """Typed instead of spoken (debug)."""

    type: Literal["text"] = "text"
    text: str


class ResetMessage(WireModel):
    type: Literal["reset"] = "reset"


VoiceClientMessage = Annotated[
    Union[StartMessage, AudioStartMessage, AudioEndMessage, TextMessage, ResetMessage],
    Field(discriminator="type"),
]

# ── Server → client ──


class ReadyMessage(WireModel):
    type: Literal["ready"] = "ready"
    session_id: str
    stt: str
    tts: str
    llm: str


class TranscriptMessage(WireModel):
    """What the caller said. While they speak (streaming STT): final=false, the whole text heard so far, sent again
    as words are recognised; `stable` is its leading part made of final words (will not change, the rest may).
    Then once final=true with the definitive text, which the agent answers."""

    type: Literal["transcript"] = "transcript"
    track: Literal["caller"] = "caller"
    text: str
    final: bool
    stable: str | None = None


class AgentTextMessage(WireModel):
    type: Literal["agent_text"] = "agent_text"
    delta: str


class AgentToolMessage(WireModel):
    """Sent twice per tool: once with `args` when called, once with `ok`/`ms` when done."""

    type: Literal["agent_tool"] = "agent_tool"
    name: str
    ok: bool | None = None
    ms: int | None = None
    args: dict[str, Any] | None = None


class AgentAudioStartMessage(WireModel):
    """Binary audio frames follow (one segment per turn)."""

    type: Literal["agent_audio_start"] = "agent_audio_start"
    mime: str


class AgentAudioEndMessage(WireModel):
    type: Literal["agent_audio_end"] = "agent_audio_end"


class AgentDoneMessage(WireModel):
    type: Literal["agent_done"] = "agent_done"
    text: str
    timings: TurnTimings


class VoiceErrorMessage(WireModel):
    type: Literal["error"] = "error"
    message: str


VoiceServerMessage = Annotated[
    Union[
        ReadyMessage,
        TranscriptMessage,
        AgentTextMessage,
        AgentToolMessage,
        AgentAudioStartMessage,
        AgentAudioEndMessage,
        AgentDoneMessage,
        VoiceErrorMessage,
    ],
    Field(discriminator="type"),
]
