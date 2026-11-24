"""
Thin HTTP client for the ERP API (routes: apps/api, contract: packages/shared/src/api.ts).
Every request carries `x-actor` so the ERP's activity feed shows what the AI did, and `x-actor-name`
percent-encoded (headers are ASCII: "Hélène" → "H%C3%A9l%C3%A8ne"; the ERP decodes it, apps/backend/app/dependencies.py).
All clients share one connection pool (`erp_http`), closed on app shutdown (app/main.py).
"""

import asyncio
from typing import Any, Literal
from urllib.parse import quote

import httpx

from app.config import settings

Actor = Literal["ai_chat", "voice_agent"]


class ErpError(Exception):
    """The ERP refused the request (its French message is given to the model) or is unreachable."""


_http: httpx.AsyncClient | None = None
_http_loop: asyncio.AbstractEventLoop | None = None


def erp_http() -> httpx.AsyncClient:
    """The shared ERP connection pool (created on first use: keep-alive saves a TCP connect per tool call).
    Pooled connections belong to one event loop: a new loop (CLI run, test) gets a new pool."""
    global _http, _http_loop
    loop = asyncio.get_running_loop()
    if _http is None or _http.is_closed or _http_loop is not loop:
        _http, _http_loop = httpx.AsyncClient(timeout=10), loop
    return _http


async def close_erp_http() -> None:
    global _http
    if _http is not None:
        await _http.aclose()
        _http = None


class ErpClient:
    def __init__(
        self,
        actor: Actor,
        actor_name: str | None = None,
        base_url: str = settings.erp_api_url,
        http: httpx.AsyncClient | None = None,  # default: the shared pool (tests pass a MockTransport client)
    ):
        self.base_url = base_url
        self.http = http
        self.headers = {"x-actor": actor, **({"x-actor-name": quote(actor_name, safe="")} if actor_name else {})}

    async def get(self, path: str, query: dict[str, Any] | None = None) -> Any:
        params = {k: str(v) for k, v in (query or {}).items() if v is not None and v != ""}
        return await self._request("GET", path, params=params)

    async def post(self, path: str, body: Any = None) -> Any:
        return await self._request("POST", path, json={} if body is None else body)

    async def patch(self, path: str, body: Any = None) -> Any:
        return await self._request("PATCH", path, json={} if body is None else body)

    async def delete(self, path: str, query: dict[str, Any] | None = None) -> Any:
        params = {k: str(v) for k, v in (query or {}).items() if v is not None and v != ""}
        return await self._request("DELETE", path, params=params)

    async def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            res = await (self.http or erp_http()).request(method, f"{self.base_url}{path}", headers=self.headers, **kwargs)
        except httpx.HTTPError as e:
            raise ErpError(f"ERP injoignable ({self.base_url}) : {e or type(e).__name__}") from e
        try:
            data = res.json()
        except ValueError:
            data = None
        if not res.is_success:
            message = ((data or {}).get("error") or {}).get("message") if isinstance(data, dict) else None
            raise ErpError(message or f"ERP HTTP {res.status_code} sur {method} {path}")
        return data


def enc(value: str) -> str:
    """Escape an id for a URL path segment (like JavaScript's encodeURIComponent)."""
    return quote(value, safe="!~*'()")


def pick(obj: dict, *keys: str) -> dict:
    """Copy some fields of an ERP object; fields it doesn't have stay absent (not null)."""
    return {k: obj[k] for k in keys if k in obj}
