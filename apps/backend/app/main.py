"""Entry point: the FastAPI app (CORS, routers, error format, OpenAPI) + `python -m app.main`.

On boot the SQLite database is loaded into memory, or seeded from the data pack if it is empty.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.config import API_PORT
from app.core.datapack import counts, reset_from_pack
from app.core.db import get_meta, is_seeded, load_all
from app.core.errors import HttpError
from app.core.listing import ListQuery
from app.core.utils import js_str
from app.dependencies import ERROR_RESPONSES
from app.routers import (
    billing,
    client_events,
    clients,
    context,
    logistics,
    orders,
    pricing,
    products,
    purchase_orders,
    stock,
    supplier_events,
    suppliers,
    system,
)

logging.basicConfig(level=logging.INFO, format="[api] %(message)s")
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    source = "existing database"
    if is_seeded():
        load_all()
    else:
        source = reset_from_pack()
    log.info("today=%s — %s: %s", get_meta()["today"], source, counts())
    warm_up()
    yield


def warm_up() -> None:
    """Build the derived indexes once at boot (movement index, sorted lists, stock levels) so the first
    list request after a start doesn't pay for them."""
    from app.services import dashboard, invoices, orders, stock

    stock.list_movements(limit=1)
    orders.orders_newest_first()
    invoices.list_invoices(ListQuery(limit=1))
    dashboard.dashboard()


app = FastAPI(
    title="Voice ERP kit — ERP API",
    version="1.0.0",
    description="Food wholesaler ERP (seafood + fresh produce). All routes are JSON under /api. "
    'Errors: {"error": {"code", "message"}}. Writes accept an `x-actor` header (user | ai_chat | voice_agent).',
    lifespan=lifespan,
    separate_input_output_schemas=False,  # one schema per model in the OpenAPI (no -Input / -Output twins)
    generate_unique_id_function=lambda route: route.name,  # operationId = the handler's function name
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=".*",
    allow_methods=["*"],
    allow_headers=["content-type", "x-actor", "x-actor-name"],
)

for router in [
    system.router,
    clients.router,
    client_events.router,
    products.router,
    suppliers.router,
    supplier_events.router,
    stock.router,
    orders.router,
    purchase_orders.router,
    billing.invoices,
    billing.payments,
    billing.receivables,
    pricing.tags,
    pricing.price_rules,
    pricing.prices,
    logistics.routes,
    logistics.route_runs,
    context.router,
]:
    app.include_router(router, responses=ERROR_RESPONSES)

# ───────── Errors: always {"error": {"code", "message"}} ─────────


def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


@app.exception_handler(HttpError)
async def business_error(_: Request, exc: HttpError):
    return error(exc.status, exc.code, exc.message)


_TYPE_NAMES = {str: "string", int: "number", float: "number", bool: "boolean", list: "array", dict: "object", type(None): "null"}
_EXPECTED = {"string_type": "string", "float_type": "number", "int_type": "number", "bool_type": "boolean",
             "list_type": "array", "model_type": "object", "dict_type": "object"}  # fmt: skip


def _message(e: dict[str, Any]) -> str:
    """A validation issue worded like the original (zod) API: "Required", "Expected number, received string"…"""
    kind, ctx = e["type"], e.get("ctx") or {}
    if kind == "missing":
        return "Required"
    if kind in _EXPECTED:
        return f"Expected {_EXPECTED[kind]}, received {_TYPE_NAMES.get(type(e.get('input')), 'unknown')}"
    if kind == "greater_than":
        return f"Number must be greater than {js_str(ctx['gt'])}"
    if kind == "greater_than_equal":
        return f"Number must be greater than or equal to {js_str(ctx['ge'])}"
    if kind == "string_too_short":
        return f"String must contain at least {ctx['min_length']} character(s)"
    if kind == "string_too_long":
        return f"String must contain at most {ctx['max_length']} character(s)"
    if kind == "literal_error":
        expected = str(ctx.get("expected", "")).replace(" or ", " | ").replace(", ", " | ")
        return f"Invalid enum value. Expected {expected}, received '{e.get('input')}'"
    return str(e["msg"]).removeprefix("Value error, ")


@app.exception_handler(RequestValidationError)
async def invalid_request(_: Request, exc: RequestValidationError):
    """400 validation_error with "field.path: message; …" (or invalid_json)."""
    issues = []
    for e in exc.errors():
        if e["type"] == "json_invalid":
            return error(400, "invalid_json", "Corps de requête JSON invalide")
        path = ".".join(str(p) for p in e["loc"][1:]) or "body"
        issues.append(f"{path}: {_message(e)}")
    return error(400, "validation_error", "; ".join(issues))


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code in (404, 405):
        return error(404, "not_found", f"Route inconnue : {request.method} {request.url.path}")
    return error(exc.status_code, "http_error", str(exc.detail))


@app.exception_handler(Exception)
async def internal_error(_: Request, exc: Exception):
    log.exception("internal error")
    return error(500, "internal_error", str(exc))


# ───────── OpenAPI: tidy for code generators (openapi-typescript) ─────────


def _tidy(node: Any) -> Any:
    """Optional fields are omitted, never null: `anyOf: [X, null]` → X. Also drop auto-generated titles."""
    if isinstance(node, list):
        return [_tidy(x) for x in node]
    if not isinstance(node, dict):
        return node
    node = {k: _tidy(v) for k, v in node.items()}
    any_of = node.get("anyOf")
    if isinstance(any_of, list) and {"type": "null"} in any_of:
        rest = [s for s in any_of if s != {"type": "null"}]
        node.pop("anyOf")
        node.update(rest[0] if len(rest) == 1 else {"anyOf": rest})
    if isinstance(node.get("properties"), dict):
        for prop in node["properties"].values():
            if isinstance(prop, dict):
                prop.pop("title", None)
    return node


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes,
                         separate_input_output_schemas=False)  # fmt: skip
    # Validation errors are returned as 400 ApiError (see invalid_request), not FastAPI's 422.
    for path in schema["paths"].values():
        for op in path.values():
            op.get("responses", {}).pop("422", None)
    for name in ("HTTPValidationError", "ValidationError"):
        schema.get("components", {}).get("schemas", {}).pop(name, None)
    app.openapi_schema = _tidy(schema)
    return app.openapi_schema


app.openapi = custom_openapi  # type: ignore[method-assign]

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=API_PORT)
