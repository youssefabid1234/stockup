"""Small request/response bodies: health, speech endpoints, errors."""

from pydantic import Field

from .base import WireModel

MOCK_TTS_MIME = "audio/x-mock-wav"
"""Mime of the mock TTS (no key configured): the bytes are a short silent WAV.
Clients should ignore the audio and speak the agent text with the browser's speechSynthesis instead."""


class ProviderInfo(WireModel):
    provider: str


class LLMInfo(WireModel):
    provider: str
    model: str


class HealthResponse(WireModel):
    ok: bool
    llm: LLMInfo
    stt: ProviderInfo
    tts: ProviderInfo
    erp_api_url: str


class SttResponse(WireModel):
    text: str
    ms: int


class TtsRequest(WireModel):
    text: str = Field(min_length=1)
    voice: str | None = None


class ErrorDetail(WireModel):
    code: str
    message: str


class ErrorResponse(WireModel):
    error: ErrorDetail

    @classmethod
    def of(cls, code: str, message: str) -> dict:
        return cls(error=ErrorDetail(code=code, message=message)).to_wire()
