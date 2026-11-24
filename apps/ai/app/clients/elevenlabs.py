"""ElevenLabs TTS, streaming endpoint: POST /v1/text-to-speech/{voice}/stream → mp3 chunks (audio/mpeg)."""

import httpx

from .base import TTSClient, TTSResult
from .french_speech import tts_text
from .http import body_chunks, http_client, post_stream


class ElevenLabsTTS(TTSClient):
    name = "elevenlabs"

    def __init__(
        self,
        api_key: str,
        model: str = "eleven_v4_turbo",  # team 12: measured ~370 ms to first byte (flash ~210 ms) but far better French
        voice: str = "YxrwjAKoUKULGd0g8K9Y",  # team 12: « Lucie », native French customer-service voice (team library)
        language: str = "fr",
        http: httpx.AsyncClient | None = None,
    ):
        self.api_key, self.model, self.voice, self.language, self.http = api_key, model, voice, language, http

    def build_body(self, text: str) -> dict:
        body = {"text": tts_text(text), "model_id": self.model}  # team 12: « T55 », « 82 % », « 8,46 € » read as words
        if "multilingual_v2" not in self.model:  # language_code is refused by eleven_multilingual_v2
            body["language_code"] = self.language
        return body

    # team 12 (Youssef): premade voice every ElevenLabs account has; used when the configured voice is not in the
    # library of the key in use (our French voices are in the team's library, not in the jury's).
    FALLBACK_VOICE = "JBFqnCBsd6RMkjVDRZzb"

    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
        chosen = voice or self.voice
        try:
            res = await self._stream(text, chosen)
        except Exception:
            if chosen == self.FALLBACK_VOICE:
                raise
            print(f"[tts] voice {chosen} unavailable with this key: premade fallback voice", flush=True)
            self.voice = self.FALLBACK_VOICE  # don't retry the missing voice on every sentence
            res = await self._stream(text, self.FALLBACK_VOICE)
        return TTSResult("audio/mpeg", body_chunks(res))

    async def _stream(self, text: str, voice: str):
        return await post_stream(
            self.http or http_client(),
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/stream?output_format=mp3_44100_128",
            who="elevenlabs tts",
            headers={"xi-api-key": self.api_key},
            json=self.build_body(text),
        )
