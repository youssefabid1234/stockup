"""/api/context: the context table (what the agents should know), linked to entities by entityType + entityId."""

from fastapi import APIRouter, Query

from app.core.listing import ListDep, Page
from app.dependencies import CtxDep, data
from app.schemas.domain import ContextEntityType, ContextEntry
from app.schemas.inputs import ContextEntryInput, ContextEntryPatch
from app.schemas.views import ContextEntrySummary, ContextForEntity, Ok
from app.services import context

router = APIRouter(prefix="/api/context", tags=["context"])


@router.get("", response_model=list[ContextEntrySummary] | Page[ContextEntrySummary])
async def list_context(
    lq: ListDep,
    entity_type: str | None = Query(None, alias="entityType", description="Comma list of company,client,supplier,product,category"),
    entity_id: str | None = Query(None, alias="entityId"),
    kind: str | None = Query(None, description="Comma list of kinds"),
    source: str | None = Query(None, description="Comma list of seed,user,ai_chat,voice_agent"),
    tag: str | None = None,
    q: str | None = Query(None, description="Accent-insensitive full text; results ranked by relevance"),
):
    """sort: title | entity | kind | tags | source | updated (default: relevance with q, else by entity).
    Envelope extras: counts (per entityType, ignoring `entityType`), countsBySource."""
    return context.list_context(
        entity_type=entity_type or None, entity_id=entity_id or None, kind=kind or None,
        source=source or None, tag=tag or None, q=q or None, lq=lq,
    )  # fmt: skip


@router.get("/for", response_model=ContextForEntity)
async def context_for_entity(entity_type: ContextEntityType = Query(alias="entityType"), id: str = ""):
    """Everything the agent should load before talking about one entity: its entries + related ones."""
    return context.context_for(entity_type, id)


@router.get("/{id}", response_model=ContextEntrySummary)
async def get_context_entry(id: str):
    return context.get_context(id)


@router.post("", response_model=ContextEntry, status_code=201)
async def create_context_entry(body: ContextEntryInput, ctx: CtxDep):
    """`source` is set from the x-actor header."""
    return context.create_context(ctx, body.data())


@router.patch("/{id}", response_model=ContextEntry)
async def update_context_entry(id: str, ctx: CtxDep, body: ContextEntryPatch | None = None):
    return context.update_context(ctx, id, data(body))


@router.delete("/{id}", response_model=Ok)
async def delete_context_entry(id: str, ctx: CtxDep):
    return context.delete_context(ctx, id)
