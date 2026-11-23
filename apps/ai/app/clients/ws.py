"""WebSocket helper for the real-time speech APIs (Soniox, Deepgram live). Plain `websockets`, no SDK."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed, ConnectionClosedError, InvalidStatus

from .http import provider_error


@asynccontextmanager
async def open_ws(url: str, headers: dict[str, str], who: str) -> AsyncIterator[ClientConnection]:
    """Connect (auth in the handshake headers); a refused handshake (401, 429…) becomes a ProviderError.
    Leaving the block (normally, on error or on cancellation = barge-in) closes the socket."""
    try:
        ws = await connect(url, additional_headers=headers, max_size=None, open_timeout=10)
    except InvalidStatus as e:
        res = e.response
        raise provider_error(who, res.status_code, (res.body or b"").decode("utf-8", "replace")) from None
    try:
        yield ws
    except ConnectionClosedError as e:  # closed by the server with an error code (bad audio, quota…)
        rcvd = e.rcvd
        raise provider_error(who, f"ws {rcvd.code if rcvd else 1006}", (rcvd.reason if rcvd else "") or "connection lost") from None
    finally:
        await ws.close()


def chunked(data: bytes, size: int = 256 * 1024) -> list[bytes]:
    """Cut a recording into frames small enough for any WebSocket API (Soniox caps a message at ~2 MB)."""
    return [data[i : i + size] for i in range(0, len(data), size)] or [b""]


async def once(*chunks: bytes) -> AsyncIterator[bytes]:
    """A finished recording as an async iterator of chunks (to reuse a live-transcription code path)."""
    for c in chunks:
        yield c


@asynccontextmanager
async def sending(ws: Any, audio: AsyncIterator[bytes], end: str) -> AsyncIterator[None]:
    """Send the audio frames then the `end` message in a background task, while the caller reads the results
    (live audio can't wait for the reader). The task is cancelled when the caller leaves the block.

    A failing audio source (the browser went away…) closes the socket, so the reader stops at once, and the
    source's own error is raised instead of a confusing "connection closed"."""

    source_error: Exception | None = None

    async def pump() -> None:
        nonlocal source_error
        try:
            async for chunk in audio:
                if chunk:
                    await ws.send(chunk)
            await ws.send(end)
        except ConnectionClosed:
            return  # the provider hung up: the reader gets its reason
        except Exception as e:
            source_error = e  # the audio source failed: stop the reader too
            await ws.close()

    task = asyncio.create_task(pump())
    try:
        yield
    finally:
        task.cancel()
        if source_error:
            raise source_error
