"""
AI service entry point: HTTP routes + WS /voice on the same port (AI_PORT, default 4100).

    uv run python -m app.main                      # or, with auto-reload:
    uv run uvicorn app.main:app --reload --port 4100

API docs: http://localhost:4100/docs — the contract (all events and WS messages) is in /openapi.json.
"""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import TypeAdapter

from app.clients import ConfigError, get_llm_client, get_stt_client, get_tts_client
from app.clients.http import http_client
from app.config import settings
from app.routers import routers
from app.tools.erp import close_erp_http
from app.schemas import ChatStreamEvent, CommandRequest, CommandStreamEvent, ErrorResponse, VoiceClientMessage, VoiceServerMessage


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:  # build the provider clients now: a missing key fails at startup, not at the first call
        llm, stt, tts = get_llm_client(), get_stt_client(), get_tts_client()
    except ConfigError as e:
        raise SystemExit(f"[ai] configuration error: {e}\n     see apps/ai/README.md and .env.example") from None
    print(f"[ai] http://localhost:{settings.port}  (WS /voice, docs /docs)")
    print(f"[ai] llm={llm.provider}:{llm.model}  stt={stt.name}  tts={tts.name}  erp={settings.erp_api_url}", flush=True)
    yield
    await http_client().aclose()
    await close_erp_http()


app = FastAPI(title="Voice ERP kit — AI service", version="0.1.0", lifespan=lifespan, separate_input_output_schemas=False)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"], expose_headers=["x-ms"])
for router in routers:
    app.include_router(router)


@app.exception_handler(RequestValidationError)
async def bad_request(_request: Request, exc: RequestValidationError) -> JSONResponse:
    """Invalid body → 400 {error: {code, message}}, the same error shape as the ERP API."""
    problems = "; ".join(f"{'.'.join(map(str, e['loc'][1:])) or 'body'}: {e['msg']}" for e in exc.errors())
    return JSONResponse(ErrorResponse.of("bad_request", problems), status_code=400)


# The streamed events and WS messages are not request/response bodies, so FastAPI would leave them out
# of /openapi.json. Add them as named schemas: the web app's TypeScript types are generated from there.
STREAM_SCHEMAS = {
    "ChatStreamEvent": ChatStreamEvent,
    "CommandStreamEvent": CommandStreamEvent,
    "VoiceClientMessage": VoiceClientMessage,
    "VoiceServerMessage": VoiceServerMessage,
    "CommandRequest": CommandRequest,
}


def openapi() -> dict:
    if not app.openapi_schema:
        schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
        components = schema.setdefault("components", {}).setdefault("schemas", {})
        for name, type_ in STREAM_SCHEMAS.items():
            json_schema = TypeAdapter(type_).json_schema(ref_template="#/components/schemas/{model}")
            components.update(json_schema.pop("$defs", {}))
            components.setdefault(name, json_schema)
        # Our validation errors are 400 ErrorResponse (see bad_request above), not FastAPI's default 422.
        for operation in (op for path in schema["paths"].values() for op in path.values()):
            if operation.get("responses", {}).pop("422", None):
                operation["responses"]["400"] = {
                    "description": "Bad request",
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}},
                }
        for unused in ("HTTPValidationError", "ValidationError"):
            components.pop(unused, None)
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = openapi

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.port)
