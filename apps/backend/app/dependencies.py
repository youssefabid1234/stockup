"""Things routers get injected or share: who is calling, request-body helpers, query parsing."""

from __future__ import annotations

import re
from typing import Annotated, Any
from urllib.parse import unquote

from fastapi import Depends, Header

from app.core.activity import Ctx
from app.core.errors import validation_error
from app.schemas.base import Input
from app.schemas.views import ApiError

ACTORS = {"user", "ai_chat", "voice_agent", "system"}


def get_ctx(
    x_actor: Annotated[str | None, Header(description="user | ai_chat | voice_agent (default user)")] = None,
    x_actor_name: Annotated[str | None, Header(description="Display name of the actor (URI-encoded)")] = None,
) -> Ctx:
    """Who is calling: `x-actor` header + optional `x-actor-name`. Recorded on every ActivityEvent."""
    actor = x_actor if x_actor in ACTORS else "user"
    return Ctx(actor=actor, actor_name=unquote(x_actor_name) if x_actor_name else None)  # type: ignore[arg-type]


CtxDep = Annotated[Ctx, Depends(get_ctx)]
"""Use in a write route: `def create(..., ctx: CtxDep)`."""


def data(body: Input | None) -> dict[str, Any]:
    """The fields sent in an optional request body, as a dict (an empty body counts as {})."""
    return body.data() if body else {}


def iso_date_query(value: str | None) -> str | None:
    """Optional YYYY-MM-DD query param (400 otherwise)."""
    if value and not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        raise validation_error("body: format AAAA-MM-JJ attendu")
    return value or None


# Documented on every route: business errors share one JSON shape.
ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    400: {"model": ApiError, "description": "Invalid request (validation_error, invalid_json, business rule)"},
    404: {"model": ApiError, "description": "Not found"},
    409: {"model": ApiError, "description": "Invalid state transition"},
}
