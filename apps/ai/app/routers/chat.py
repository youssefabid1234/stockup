"""POST /chat: the agent, streamed as Server-Sent Events."""

from fastapi import APIRouter

from app.agent import call_context as preload
from app.agent import run_agent, sanitize_history
from app.clients import get_llm_client
from app.schemas import ChatRequest
from app.tools import ErpClient, all_tools

from .sse import sse_doc, sse_response

router = APIRouter(tags=["agent"])


@router.post("/chat", responses=sse_doc("ChatStreamEvent"))
async def chat(body: ChatRequest):
    """ChatRequest → text/event-stream of ChatStreamEvent."""
    # The harness owns the system prompt; a client-rebuilt history with a broken tool pairing must not 400 the provider.
    messages = sanitize_history(body.messages)
    # Team 12 (Youssef): caller ID (chosen explicitly) → their sheet is in the prompt from the very first turn
    extra = {}
    if body.caller_client_id:
        sheet = await preload.caller_context(ErpClient("ai_chat"), client_id=body.caller_client_id)
        extra = {"call_context": sheet} if sheet else {}
    return sse_response(
        run_agent(messages, llm=get_llm_client(), tools=all_tools(), mode=body.mode or "chat", actor_name=body.actor_name, **extra)
    )
