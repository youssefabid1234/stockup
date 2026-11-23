"""
Gradium TTS and STT, REST endpoints (auth: x-api-key). Docs: https://docs.gradium.ai

TTS  POST https://api.gradium.ai/api/speech/tts  {text, voice_id, output_format, model_name, only_audio: false}
     → NDJSON stream: {"type": "audio", "audio": <base64>} … ({"type": "text"} timestamps, {"type": "error"}).
     Gradium has no mp3 output (wav / pcm / ogg-opus), and the web player streams mp3, so we ask for raw PCM
     (48 kHz, 16-bit mono) and encode it to mp3 chunk by chunk: the first audio still leaves after ~one chunk.
     The voice sets the language: pick a French voice (default Armand, a flagship fr-FR voice).

STT  POST https://api.gradium.ai/api/speech/asr?json_config={"language": "fr", …}  raw audio body
     → NDJSON: {"type": "text", "text": "…"} per segment, {"type": "end_text"}, maybe {"type": "error"}.
     Accepts wav, raw pcm and Ogg/Opus only: the browser's WebM/Opus is re-wrapped into Ogg (audio.py, no re-encoding).
     Safari's audio/mp4 (AAC) is not accepted.

Errors before the stream starts come back as HTTP 500, plain text "error from server 1008: API key is revoked…".
"""

import base64
import json
from collections.abc import AsyncIterator

import httpx

from .audio import AudioFormatError, Mp3Encoder, webm_to_ogg
from .base import STTClient, TTSClient, TTSResult
from .http import check_ok, http_client, post_stream, provider_error

BASE = "https://api.gradium.ai/api"
PCM_RATE = 48000  # output_format "pcm" = 48 kHz, 16-bit signed little-endian mono, 80 ms chunks


class GradiumTTS(TTSClient):
    name = "gradium"

    def __init__(self, api_key: str, model: str = "default", voice: str = "F7Iib4MAyHIRed0x", http: httpx.AsyncClient | None = None):
        self.api_key, self.model, self.voice, self.http = api_key, model, voice, http

    def build_body(self, text: str, voice: str | None) -> dict:
        return {"text": text, "voice_id": voice or self.voice, "model_name": self.model, "output_format": "pcm", "only_audio": False}

    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
        res = await post_stream(
            self.http or http_client(),
            f"{BASE}/speech/tts",
            who="gradium tts",
            headers={"x-api-key": self.api_key},
            json=self.build_body(text, voice),
        )
        return TTSResult("audio/mpeg", mp3_chunks(res))


async def mp3_chunks(res: httpx.Response) -> AsyncIterator[bytes]:
    """Gradium's NDJSON audio messages (base64 PCM) → mp3 bytes as they arrive."""
    mp3 = Mp3Encoder(PCM_RATE)
    try:
        async for line in res.aiter_lines():
            if not line.strip():
                continue
            msg = json.loads(line)
            if msg.get("type") == "audio":
                if out := mp3.encode(base64.b64decode(msg.get("audio") or "")):
                    yield out
            elif msg.get("type") == "error":
                raise provider_error("gradium tts", msg.get("code") or "stream", msg.get("message") or line)
        if out := mp3.flush():
            yield out
    finally:
        await res.aclose()


class GradiumSTT(STTClient):
    name = "gradium"

    def __init__(self, api_key: str, model: str = "default", language: str = "fr", http: httpx.AsyncClient | None = None):
        self.api_key, self.model, self.language, self.http = api_key, model, language, http

    def build_config(self, hint: str | None) -> dict:
        config: dict = {"language": self.language}
        # Keyword boosting: single words only (multi-word names are split), max 500, boost 3 = recommended default.
        words = list(dict.fromkeys(w for term in (hint or "").split(",") for w in term.split()))
        if words:
            config["keywords"] = {"words": words[:500], "boost": 3}
        return config

    @staticmethod
    def prepare(audio: bytes, mime: str) -> tuple[bytes, str]:
        """The recording in a format Gradium accepts, with its content type."""
        mime = mime.lower()
        try:
            if "webm" in mime:
                return webm_to_ogg(audio), "audio/ogg"
        except AudioFormatError as e:
            raise provider_error("gradium stt", 415, f"cannot convert {mime}: {e}") from None
        for kind in ("ogg", "opus", "wav", "pcm"):
            if kind in mime:
                return audio, "audio/ogg" if kind == "opus" else f"audio/{kind}"
        raise provider_error("gradium stt", 415, f"{mime} unsupported (Gradium takes wav, pcm, ogg/opus; record with Chrome or Firefox)")

    async def transcribe(self, audio: bytes, mime: str, hint: str | None = None) -> str:
        body, content_type = self.prepare(audio, mime)
        res = await (self.http or http_client()).post(
            f"{BASE}/speech/asr",
            params={"model": self.model, "json_config": json.dumps(self.build_config(hint), ensure_ascii=False)},
            headers={"x-api-key": self.api_key, "content-type": content_type},
            content=body,
        )
        await check_ok(res, "gradium stt")
        parts = []
        for line in res.text.splitlines():
            if not line.strip():
                continue
            msg = json.loads(line)
            if msg.get("type") == "text":
                parts.append(msg.get("text") or "")
            elif msg.get("type") == "error":
                raise provider_error("gradium stt", "stream", msg.get("message") or line)
        return " ".join(" ".join(parts).split())
