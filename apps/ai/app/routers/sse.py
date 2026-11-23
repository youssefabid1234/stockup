"""Server-Sent Events: one JSON event per `data:` line, as the web app's EventSource-style reader expects."""

from collections.abc import AsyncIterator

from fastapi.responses import StreamingResponse

from app.schemas.base import WireModel


def sse_response(events: AsyncIterator[WireModel]) -> StreamingResponse:
    async def frames() -> AsyncIterator[str]:
        async for ev in events:
            yield f"data: {ev.to_json()}\n\n"

    # If the client disconnects, Starlette cancels this generator: the agent run stops with it.
    return StreamingResponse(frames(), media_type="text/event-stream", headers={"cache-control": "no-cache"})


def sse_doc(schema_name: str) -> dict:
    """OpenAPI description of an SSE response whose events are `schema_name` (see main.py)."""
    return {200: {"description": f"text/event-stream, one {schema_name} JSON per `data:` line",
                  "content": {"text/event-stream": {"schema": {"$ref": f"#/components/schemas/{schema_name}"}}}}}  # fmt: skip
