"""
Context tools: the business knowledge table (company rules, a client's habits and people, a supplier's
negotiation style, product aliases, category cards…). Search it, load everything about one entity before
answering, and save a new fact learned during a chat or a call.
"""

from typing import Literal

from pydantic import Field

from .history import without_none
from .registry import ToolContext, tool

EntityType = Literal["company", "client", "supplier", "product", "category"]
Kind = Literal["policy", "procedure", "preference", "fact", "relationship", "pricing", "logistics", "risk"]


def clip(s: str, n: int) -> str:
    return f"{s[:n]}…" if len(s) > n else s


def compact(e: dict, body_max: int = 700) -> dict:
    """One compact entry for the model."""
    source = e.get("source")
    return {
        "id": e["id"],
        "about": e.get("entityLabel") if "entityLabel" in e else e.get("entityId") or "Company",
        "kind": e.get("kind"),
        "title": e.get("title"),
        "body": clip(e.get("body") or "", body_max),
        **({"source": source} if source and source != "seed" else {}),
    }


@tool
async def search_context(
    ctx: ToolContext,
    query: str = Field(description="Keywords in English, e.g. \"substitution\", \"remission\", \"limit time\""),
    entity_type: EntityType | None = Field(None, description="Optional: limit to one type of sheet"),
    entity_id: str | None = Field(None, description="Optional: limit to an entity (cli_..., su_..., prd_... or a category)"),
    kind: Kind | None = Field(None, description="Optional: limit to a type of sheet"),
    limit: float | None = Field(None, description="Max number of cards (default 6)"),
) -> list[dict]:
    """
    Search in the company context sheets (rules, procedures, customer habits and preferences, people,
    negotiation suppliers, alias products, deliveries, prices, risks). Full text search without accents, results by relevance.
    To be used for a question of rule or know-how ("can we make a discount?", "Paris Sud time limit?").
    Search the company context facts.
    """
    query_params = {"q": query, "entityType": entity_type, "entityId": entity_id, "kind": kind, "limit": int(limit or 6)}
    rows = await ctx.erp.get("/api/context", query_params)
    return [compact(e, 500) for e in rows]


@tool
async def get_context(
    ctx: ToolContext,
    entity_type: Literal["client", "supplier", "product", "category"],
    id: str = Field(description="cli_0012, sup_0003, prd_0005 or a category id (see GET /api/categories)"),
) -> dict:
    """
    The whole context of a customer, supplier, product or radius: profile, people and way of speaking, habits, which irritates them,
    open files, how to talk to them, price agreements (+ linked cards: product radius, company rules that quote it).
    À charger avant de répondre à un client ou de parler d'un produit. Load everything known about one entity.
    """
    r = await ctx.erp.get("/api/context/for", {"entityType": entity_type, "id": id})
    return {
        "about": r.get("label"),
        "entries": [compact(e) for e in r["entries"]],
        "related": [compact(e, 400) for e in r["related"]],
    }


@tool
async def save_context(
    ctx: ToolContext,
    entity_type: EntityType,
    kind: Kind,
    title: str = Field(description="Short title, e.g. \"Delivery by service door\""),
    body: str = Field(description="The fact, in English, 1 to 3 sentences (light markdown)"),
    entity_id: str | None = Field(None, description="Required except for company: cli_..., sup_..., prd_... or a category"),
    tags: list[str] | None = Field(None, description="Optional: keywords"),
) -> dict:
    """
    Memorizes a lasting fact learned during the exchange (preference, habit, contact, delivery constraint...) in context sheets,
    so that the team and future calls know. Not for a complaint or incident (uses log_client_event).
    Formulate it in a clear sentence, without inventing. Remember has durable fact.
    """
    entry = {"entityType": entity_type, "entityId": entity_id, "kind": kind, "title": title, "body": body, "tags": tags}
    e = await ctx.erp.post("/api/context", without_none(entry))
    return {"id": e["id"], "saved": True, "title": e.get("title")}
