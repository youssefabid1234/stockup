"""
Voice COMMAND contract (POST /command[?speak=1]): one utterance → one action → one line.

Body: raw audio (content-type audio/webm|wav…, header x-mock-text for the mock STT) or JSON CommandRequest.
Stream: transcript → (text | tool_call | tool_result)* → navigate? → speech? → done (with timings) | error.
WS /voice/command streams the audio instead (live transcript): same events, preceded by transcript final=false ones.
"""

from typing import Annotated, Literal, Union

from pydantic import Field

from .base import WireModel
from .chat import DoneEvent, ErrorEvent, TextEvent, ToolCallEvent, ToolResultEvent


class CommandRequest(WireModel):
    text: str
    actor_name: str | None = None


class TranscriptEvent(WireModel):
    """ms = STT time (0 for typed text). The final one (final=true) comes before the agent's events.
    WS /voice/command also sends final=false ones while the user speaks: the text heard so far, `stable` = its
    leading part made of final words (will not change)."""

    type: Literal["transcript"] = "transcript"
    text: str
    ms: int
    final: bool = True
    stable: str | None = None


class NavigateEvent(WireModel):
    """The user asked to SEE an entity: web route to open (e.g. /products/prd_0012)."""

    type: Literal["navigate"] = "navigate"
    path: str
    label: str | None = None


class SpeechEvent(WireModel):
    """?speak=1: base64 audio of the answer. mime MOCK_TTS_MIME → speak the text with speechSynthesis."""

    type: Literal["speech"] = "speech"
    mime: str
    audio: str
    ms: int


CommandStreamEvent = Annotated[
    Union[TextEvent, ToolCallEvent, ToolResultEvent, DoneEvent, ErrorEvent, TranscriptEvent, NavigateEvent, SpeechEvent],
    Field(discriminator="type"),
]
