"""GET /health and GET /tools."""

from fastapi import APIRouter

from app.clients import get_llm_client, get_stt_client, get_tts_client
from app.config import settings
from app.schemas import HealthResponse, LLMInfo, ProviderInfo, ToolInfo
from app.tools import all_tools

router = APIRouter(tags=["service"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    llm = get_llm_client()
    return HealthResponse(
        ok=True,
        llm=LLMInfo(provider=llm.provider, model=llm.model),
        stt=ProviderInfo(provider=get_stt_client().name),
        tts=ProviderInfo(provider=get_tts_client().name),
        erp_api_url=settings.erp_api_url,
    )


@router.get("/tools", response_model=list[ToolInfo])
async def tools() -> list[ToolInfo]:
    """The tools the agent exposes to the model (name, description, JSON schema)."""
    return [t.info for t in all_tools()]
