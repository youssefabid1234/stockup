"""POST /chat: the agent, streamed as Server-Sent Events."""

from fastapi import APIRouter

from app.agent import run_agent, sanitize_history
from app.clients import get_llm_client
from app.schemas import ChatRequest
from app.tools import all_tools

from .sse import sse_doc, sse_response

router = APIRouter(tags=["agent"])


@router.post("/chat", responses=sse_doc("ChatStreamEvent"))
async def chat(body: ChatRequest):
    """ChatRequest → text/event-stream of ChatStreamEvent."""
    # The harness owns the system prompt; a client-rebuilt history with a broken tool pairing must not 400 the provider.
    messages = sanitize_history(body.messages)
    return sse_response(
        run_agent(messages, llm=get_llm_client(), tools=all_tools(), mode=body.mode or "chat", actor_name=body.actor_name)
    )
