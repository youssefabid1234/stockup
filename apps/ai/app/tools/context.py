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
        "about": e.get("entityLabel") if "entityLabel" in e else e.get("entityId") or "Entreprise",
        "kind": e.get("kind"),
        "title": e.get("title"),
        "body": clip(e.get("body") or "", body_max),
        **({"source": source} if source and source != "seed" else {}),
    }


@tool
async def search_context(
    ctx: ToolContext,
    query: str = Field(description="Mots-clés en français, ex. « substitution », « remise », « heure limite »"),
    entity_type: EntityType | None = Field(None, description="Optionnel : limiter à un type de fiche"),
    entity_id: str | None = Field(None, description="Optionnel : limiter à une entité (cli_…, sup_…, prd_… ou une catégorie)"),
    kind: Kind | None = Field(None, description="Optionnel : limiter à un genre de fiche"),
    limit: float | None = Field(None, description="Nombre max de fiches (défaut 6)"),
) -> list[dict]:
    """
    Cherche dans les fiches de contexte de l'entreprise (règles, procédures, habitudes et préférences des clients, personnes,
    négociation fournisseurs, alias produits, livraisons, prix, risques). Recherche plein texte sans accents, résultats par pertinence.
    À utiliser pour une question de règle ou de savoir-faire (« peut-on faire une remise ? », « heure limite Paris Sud ? »).
    Search the company context facts.
    """
    query_params = {"q": query, "entityType": entity_type, "entityId": entity_id, "kind": kind, "limit": int(limit or 6)}
    rows = await ctx.erp.get("/api/context", query_params)
    return [compact(e, 500) for e in rows]


@tool
async def get_context(
    ctx: ToolContext,
    entity_type: Literal["client", "supplier", "product", "category"],
    id: str = Field(description="cli_0012, sup_0003, prd_0005 ou un id de catégorie (voir GET /api/categories)"),
) -> dict:
    """
    Tout le contexte d'un client, fournisseur, produit ou rayon : profil, personnes et façon de parler, habitudes, ce qui les agace,
    dossiers ouverts, comment leur parler, accords de prix (+ fiches liées : rayon du produit, règles d'entreprise qui le citent).
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
    title: str = Field(description="Titre court, ex. « Livraison par la porte de service »"),
    body: str = Field(description="Le fait, en français, 1 à 3 phrases (markdown léger)"),
    entity_id: str | None = Field(None, description="Requis sauf pour company : cli_…, sup_…, prd_… ou une catégorie"),
    tags: list[str] | None = Field(None, description="Optionnel : mots-clés"),
) -> dict:
    """
    Mémorise un fait durable appris pendant l'échange (préférence, habitude, contact, contrainte de livraison…) dans les fiches de contexte,
    pour que l'équipe et les prochains appels le sachent. Pas pour une réclamation ou un incident (utilise log_client_event).
    Formule-le en une phrase claire, sans inventer. Remember a durable fact.
    """
    entry = {"entityType": entity_type, "entityId": entity_id, "kind": kind, "title": title, "body": body, "tags": tags}
    e = await ctx.erp.post("/api/context", without_none(entry))
    return {"id": e["id"], "saved": True, "title": e.get("title")}
