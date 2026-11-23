"""
One push-to-talk utterance, transcribed WHILE it is recorded (used by WS /voice and WS /voice/command).

    audio_start  → Utterance(stt, mime, hint, on_partial)   opens the provider stream (if stt.streams)
    binary frame → feed(frame)                              forwarded to the provider at once
                     … on_partial(STTUpdate)                partial transcripts, to show while the caller speaks
    audio_end    → await text()                             end of audio: only the last words are left to finalize

With a streaming STT (Soniox, Deepgram, mock) the transcript is ready a few hundred ms after the release, instead
of transcribing the whole recording then. Every frame is also kept: if the live stream breaks (network, provider
error, no final words in time), text() transcribes the whole recording the classic way, so the utterance is never
lost. cancel() (barge-in, client gone) closes the provider stream.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import aclosing

from app.clients import STTClient
from app.clients.base import STTUpdate

from .vocabulary import stt_hint

FINAL_TIMEOUT_S = 5.0  # after audio_end, how long to wait for the live stream's final words before the fallback


class Utterance:
    def __init__(self, stt: STTClient, mime: str, hint: str | None, on_partial: Callable[[STTUpdate], Awaitable[None]]):
        self.stt, self.mime, self.hint, self.on_partial = stt, mime, hint, on_partial
        self.frames: list[bytes] = []
        self.queue: asyncio.Queue[bytes | None] = asyncio.Queue()  # frames for the live stream, None = end of audio
        self.live = asyncio.create_task(self._listen()) if stt.streams else None

    def feed(self, frame: bytes) -> None:
        self.frames.append(frame)
        self.queue.put_nowait(frame)

    async def text(self) -> str:
        """Call at audio_end: the final transcript."""
        self.queue.put_nowait(None)
        if self.live:
            try:
                return await asyncio.wait_for(self.live, FINAL_TIMEOUT_S)  # on timeout the stream is cancelled
            except Exception as e:
                print(f"[ai] live STT failed ({type(e).__name__}: {e}): transcribing the whole recording", flush=True)
        hint = await stt_hint(self.stt.name, self.hint)
        return await self.stt.transcribe(b"".join(self.frames), self.mime, hint)

    def cancel(self) -> None:
        if not self.live:
            return
        if not self.live.done():
            self.live.cancel()
        elif not self.live.cancelled():
            self.live.exception()  # a stream that already failed: nobody will read it, that's fine

    async def _audio(self) -> AsyncIterator[bytes]:
        while (frame := await self.queue.get()) is not None:
            yield frame

    async def _listen(self) -> str:
        hint = await stt_hint(self.stt.name, self.hint)  # cached; frames wait in the queue meanwhile
        shown = None
        # aclosing: leaving early (final words, cancellation) closes the provider's socket right away
        async with aclosing(self.stt.transcribe_stream(self._audio(), self.mime, hint)) as updates:  # type: ignore[type-var]
            async for update in updates:
                if update.final:
                    return update.text
                if update.text != shown:
                    shown = update.text
                    await self.on_partial(update)
        return shown or ""
