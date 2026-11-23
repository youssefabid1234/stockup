"""
Mock speech, so the voice pipeline runs with no keys.
  - STT returns the hint if given (POST /stt header `x-mock-text`), else MOCK_STT_TEXT. Live, it "hears" that
    text one word every few audio chunks (provisional), so partial transcripts show up in the UI with no key.
  - TTS returns a short silent WAV with mime MOCK_TTS_MIME: the web app then speaks the text
    with the browser's speechSynthesis.
"""

import struct
from collections.abc import AsyncIterator

from app.schemas import MOCK_TTS_MIME

from .base import STTClient, STTUpdate, TTSClient, TTSResult


class MockSTT(STTClient):
    name = "mock"
    streams = True

    def __init__(self, fixed_text: str, chunks_per_word: int = 3):
        self.fixed_text, self.chunks_per_word = fixed_text, chunks_per_word

    async def transcribe(self, audio: bytes, mime: str, hint: str | None = None) -> str:
        return hint or self.fixed_text

    async def transcribe_stream(self, audio: AsyncIterator[bytes], mime: str, hint: str | None = None) -> AsyncIterator[STTUpdate]:
        """One more word every `chunks_per_word` chunks (~300 ms of MediaRecorder audio); all but the last
        word heard are "final". The whole text once the audio ends."""
        words, chunks = (hint or self.fixed_text).split(), 0
        async for _ in audio:
            chunks += 1
            heard = min(len(words), chunks // self.chunks_per_word)
            if heard and chunks % self.chunks_per_word == 0:
                yield STTUpdate(" ".join(words[:heard]), stable=" ".join(words[: heard - 1]))
        text = " ".join(words)
        yield STTUpdate(text, final=True, stable=text)


class MockTTS(TTSClient):
    name = "mock"

    async def synthesize(self, text: str, voice: str | None = None) -> TTSResult:
        async def chunks() -> AsyncIterator[bytes]:
            yield silent_wav(0.1)

        return TTSResult(MOCK_TTS_MIME, chunks())


def silent_wav(seconds: float, sample_rate: int = 16000) -> bytes:
    """16 kHz, 16-bit mono PCM WAV of silence."""
    data_bytes = round(seconds * sample_rate) * 2
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_bytes, b"WAVE",
        b"fmt ", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16,  # PCM, mono, byte rate, block align, bits/sample
        b"data", data_bytes,
    )
    return header + bytes(data_bytes)
