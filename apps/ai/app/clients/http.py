"""Small httpx helpers shared by the provider adapters (no SDKs: every call is visible)."""

import itertools
import json
import time
from collections.abc import AsyncIterator
from typing import Any

import httpx

# One shared connection pool: reusing connections saves a TLS handshake per call (matters for voice latency).
# `read` is the max silence between two chunks of a stream, generous for "thinking" models.
_client: httpx.AsyncClient | None = None


def http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(120, connect=10))
    return _client


class ProviderError(Exception):
    """A provider answered with an HTTP error."""


def provider_error(who: str, status: int | str, body: str, limit: int = 300) -> ProviderError:
    """One error message format for every provider: "<who> HTTP <status>: <body>", with a hint the UI can show
    in front for the usual causes (bad key, rate limit / quota, audio format)."""
    hint = error_hint(status, body)
    return ProviderError(f"{who} HTTP {status}: {body[:limit]}" + (f" — {hint}" if hint else ""))


def error_hint(status: int | str, body: str) -> str:
    low = body.lower()
    if status in (401, 403) or "api key" in low or "unauthori" in low:
        return "clé API refusée (vérifiez STT_API_KEY / TTS_API_KEY)"
    if status in (402, 429) or "quota" in low or "rate limit" in low or "credit" in low:
        return "limite de débit ou quota atteint : réessayez dans un instant"
    if status == 415 or "decode" in low or "unsupported" in low or "format" in low:
        return "format audio non supporté par ce fournisseur"
    return ""


async def check_ok(res: httpx.Response, who: str, limit: int = 300) -> None:
    """Raise ProviderError with the start of the body if the status is not 2xx (works on streamed responses)."""
    if res.is_success:
        return
    body = (await res.aread()).decode("utf-8", "replace")
    await res.aclose()
    raise provider_error(who, res.status_code, body, limit)


async def post_stream(
    client: httpx.AsyncClient, url: str, *, who: str | None = None, limit: int = 300, **kwargs: Any
) -> httpx.Response:
    """POST and return the response *without* reading the body yet (streaming). Close it when done."""
    res = await client.send(client.build_request("POST", url, **kwargs), stream=True)
    await check_ok(res, who or httpx.URL(url).netloc.decode(), limit)
    return res


async def sse_json(res: httpx.Response) -> AsyncIterator[Any]:
    """Iterate the `data:` payloads of a Server-Sent Events response, parsed as JSON. "[DONE]" ends it."""
    try:
        async for line in res.aiter_lines():
            if not line.startswith("data:"):
                continue  # comments, "event:" lines, blank separators
            data = line[5:].strip()
            if not data:
                continue
            if data == "[DONE]":
                return
            try:
                yield json.loads(data)
            except json.JSONDecodeError:
                pass  # keep-alives / partial garbage
    finally:
        await res.aclose()


async def body_chunks(res: httpx.Response) -> AsyncIterator[bytes]:
    """The raw body of a streamed response, chunk by chunk."""
    try:
        async for chunk in res.aiter_bytes():
            yield chunk
    finally:
        await res.aclose()


def parse_args(raw: str | None) -> dict[str, Any]:
    """Parse tool-call arguments that arrive as a JSON string; never raise."""
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


_counter = itertools.count()


def new_call_id(prefix: str = "call") -> str:
    """A unique id for providers that don't give one (Gemini, the mock): prefix_<time36>_<counter36>."""
    return f"{prefix}_{_base36(int(time.time() * 1000))}_{_base36(next(_counter))}"


def _base36(n: int) -> str:
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while True:
        n, r = divmod(n, 36)
        out = digits[r] + out
        if not n:
            return out
