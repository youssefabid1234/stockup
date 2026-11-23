"""Context table: short, structured facts the agents should know (company rules, a client's habits and
people, a supplier's negotiation style, product aliases, category cards…). Seeded from the data pack;
editable in the UI and writable by the agents (save_context) during a chat or a call.

Each entry is linked to what it is about by `entityType` (company | client | supplier | product |
category) + `entityId` (absent for company; a ProductCategory for category).

Search is accent-insensitive full text (title weighs more than body and tags); with `q`, results are
ranked by relevance, otherwise grouped by entity type and entity.
"""

from __future__ import annotations

from app import crud
from app.core.activity import Ctx, log_event, now
from app.core.db import Doc, transactional
from app.core.errors import bad_request
from app.core.listing import Key, ListQuery, apply_sort, count_by, respond
from app.core.utils import cmp, collate_key, js_round, normalize, sort_by

ENTITY_TYPES = ["company", "client", "supplier", "product", "category"]
KINDS = ["policy", "procedure", "preference", "fact", "relationship", "pricing", "logistics", "risk"]


_TYPE_ORDER = {t: i for i, t in enumerate(ENTITY_TYPES)}
# Words ignored in a context query.
_STOP = {"le", "la", "les", "de", "des", "du", "un", "une", "et", "a", "au", "aux", "en", "pour", "sur", "est", "qui", "que", "d", "l"}


def entity_label(entity_type: str, id: str | None = None) -> str | None:
    """Name of the entity an entry is about, or None if it does not exist."""
    if entity_type == "company":
        return "Entreprise"
    if not id:
        return None
    if entity_type == "category":
        from app.services.categories import category_map

        return category_map().get(id)
    table = {"client": crud.clients, "supplier": crud.suppliers, "product": crud.products}.get(entity_type)
    doc = table.get(id) if table else None
    return doc["name"] if doc else None


def _check_target(entity_type: str, entity_id: str | None) -> None:
    """400 unless the pair is valid (company: no entityId; others: an existing id)."""
    if entity_type == "company":
        if entity_id:
            raise bad_request("invalid_entity", "Une fiche « entreprise » ne se rattache à aucune entité (entityId interdit)")
        return
    if not entity_id:
        raise bad_request("invalid_entity", f"entityId requis pour une fiche « {entity_type} »")
    if not entity_label(entity_type, entity_id):
        raise bad_request("invalid_entity", f"Entité inconnue ({entity_type}) : {entity_id}")


def context_summary(e: Doc, score: float | None = None) -> Doc:
    label = entity_label(e["entityType"], e.get("entityId")) or e.get("entityId") or "?"
    return {**e, "entityLabel": label, **({"score": score} if score is not None else {})}


def _score(e: Doc, tokens: list[str]) -> float:
    """Relevance for normalised query tokens: every token must appear somewhere (title, tags, entity, body)."""
    title = normalize(e["title"])
    tags = normalize(" ".join(e.get("tags") or []))
    ent = normalize(entity_label(e["entityType"], e.get("entityId")) or "")
    body = normalize(e["body"])
    s = 0.0
    for t in tokens:
        in_title, in_tags, in_ent, in_body = t in title, t in tags, t in ent, t in body
        if not (in_title or in_tags or in_ent or in_body):
            return 0
        s += (5 if in_title else 0) + (3 if in_tags else 0) + (3 if in_ent else 0)
        if in_body:
            s += 1 + min(3, body.count(t) - 1) * 0.5
    return js_round(s * 10) / 10


def _set(v: str | None) -> set[str] | None:
    return {x.strip() for x in v.split(",") if x.strip()} if v else None


CONTEXT_SORTS: dict[str, Key] = {
    "title": lambda e: collate_key(e["title"]),
    "entity": lambda e: (_TYPE_ORDER[e["entityType"]], collate_key(entity_label(e["entityType"], e.get("entityId")) or "")),
    "kind": lambda e: e["kind"],
    "tags": lambda e: ",".join(e.get("tags") or []),
    "source": lambda e: e.get("source") or "seed",
    "updated": lambda e: e.get("updatedAt"),
}


def list_context(entity_type: str | None = None, entity_id: str | None = None, kind: str | None = None,
                 source: str | None = None, tag: str | None = None, q: str | None = None,
                 limit: int | None = None, lq: ListQuery | None = None) -> list[Doc] | Doc:  # fmt: skip
    """GET /api/context — entityType/kind/source are comma lists. With q: by relevance; else grouped by
    entity type and entity. Envelope extras: counts per entityType (ignoring `entityType`), countsBySource."""
    if lq is None:  # internal callers: every entry
        lq = ListQuery(limit=limit or 10**9)
    types, kinds, sources = _set(entity_type), _set(kind), _set(source)
    tokens = [t for t in normalize(q).split(" ") if t and t not in _STOP] if q else []
    base: list[tuple[Doc, float | None]] = []
    for e in crud.context_entries.rows.values():
        if entity_id and e.get("entityId") != entity_id:
            continue
        if kinds and e["kind"] not in kinds:
            continue
        if sources and e.get("source", "seed") not in sources:
            continue
        if tag and tag not in (e.get("tags") or []):
            continue
        if tokens:
            score = _score(e, tokens)
            if score:
                base.append((e, score))
        else:
            base.append((e, None))
    if tokens:
        base.sort(key=lambda r: (-r[1], r[0]["id"]))  # type: ignore[operator]
    else:
        base.sort(key=lambda r: (_TYPE_ORDER[r[0]["entityType"]], r[0].get("entityId") or "", r[0]["id"]))
    rows = [r for r in base if r[0]["entityType"] in types] if types else base
    rows = apply_sort(rows, lq, {k: (lambda f: lambda r: f(r[0]))(f) for k, f in CONTEXT_SORTS.items()})
    return respond(rows, lq, lambda r: context_summary(*r), lambda: {
        "counts": count_by(base, lambda r: r[0]["entityType"]),
        "countsBySource": count_by(base, lambda r: r[0].get("source", "seed")),
    })


def get_context(id: str) -> Doc:
    return context_summary(crud.context_entries.require(id))


def context_for(entity_type: str, id: str) -> Doc:
    """GET /api/context/for — what the agent should load before talking about one entity: its own
    entries, plus related ones (product → its category; supplier → the categories it sells;
    any entity → company / category entries whose body cites its id, e.g. "cli_0004")."""
    if entity_type == "company":
        return {"entityType": entity_type, "id": "", "label": "Entreprise", "entries": list_context(entity_type="company"), "related": []}
    _check_target(entity_type, id)
    entries = list_context(entity_type=entity_type, entity_id=id)
    related_categories: set[str] = set()
    if entity_type == "product":
        related_categories.add(crud.products.require(id)["category"])
    if entity_type == "supplier":
        related_categories.update(crud.suppliers.require(id)["categories"])
    seen = {e["id"] for e in entries}
    related = []
    for e in crud.context_entries.rows.values():
        if e["id"] in seen:
            continue
        is_category = e["entityType"] == "category" and (e.get("entityId") or "") in related_categories
        cites = e["entityType"] in ("company", "category") and id in e["body"]
        if is_category or cites:
            related.append(context_summary(e))
            seen.add(e["id"])
    related = sort_by(related, lambda a, b: cmp(_TYPE_ORDER[b["entityType"]], _TYPE_ORDER[a["entityType"]]) or cmp(a["id"], b["id"]))
    return {"entityType": entity_type, "id": id, "label": entity_label(entity_type, id), "entries": entries, "related": related}


def _source_of(ctx: Ctx) -> str:
    return ctx.actor if ctx.actor in ("ai_chat", "voice_agent") else "user"


def _clean_tags(tags: list[str] | None) -> list[str] | None:
    """Trimmed, deduplicated, non-empty tags (None if nothing is left)."""
    out: list[str] = []
    for t in tags or []:
        t = t.strip()
        if t and t not in out:
            out.append(t)
    return out or None


def _about(e: Doc) -> str:
    if e["entityType"] == "company":
        return "l'entreprise"
    return entity_label(e["entityType"], e.get("entityId")) or str(e.get("entityId"))


@transactional
def create_context(ctx: Ctx, input: Doc) -> Doc:
    _check_target(input["entityType"], input.get("entityId"))
    at = now()
    tags = _clean_tags(input.get("tags"))
    entry = {
        "id": crud.context_entries.next_id("ctx_", 4),
        "entityType": input["entityType"],
        **({"entityId": input["entityId"]} if input["entityType"] != "company" and input.get("entityId") else {}),
        "kind": input["kind"],
        "title": input["title"].strip(),
        "body": input["body"].strip(),
        **({"tags": tags} if tags else {}),
        "source": _source_of(ctx),
        "createdAt": at,
        "updatedAt": at,
    }
    crud.context_entries.put(entry)
    log_event(ctx, "context.created", "context", entry["id"], f"Contexte ajouté pour {_about(entry)} : « {entry['title']} »")
    return entry


@transactional
def update_context(ctx: Ctx, id: str, patch: Doc) -> Doc:
    cur = crud.context_entries.require(id)
    entity_type = patch.get("entityType") or cur["entityType"]
    if entity_type == "company":
        entity_id = None
    elif patch.get("entityId"):
        entity_id = patch["entityId"]
    elif patch.get("entityType") and patch["entityType"] != cur["entityType"]:
        entity_id = None  # changed type without a new id
    else:
        entity_id = cur.get("entityId")
    _check_target(entity_type, entity_id)
    updated = {
        **cur,
        "entityType": entity_type,
        "kind": patch.get("kind") or cur["kind"],
        "title": patch["title"].strip() if "title" in patch else cur["title"],
        "body": patch["body"].strip() if "body" in patch else cur["body"],
        "updatedAt": now(),
    }
    updated.pop("entityId", None)
    if entity_id:
        updated["entityId"] = entity_id
    if "tags" in patch:
        updated.pop("tags", None)
        tags = _clean_tags(patch["tags"])
        if tags:
            updated["tags"] = tags
    if not updated["title"] or not updated["body"]:
        raise bad_request("invalid_context", "Titre et contenu requis")
    crud.context_entries.put(updated)
    log_event(ctx, "context.updated", "context", id, f"Contexte modifié pour {_about(updated)} : « {updated['title']} »")
    return updated


@transactional
def delete_context(ctx: Ctx, id: str) -> Doc:
    cur = crud.context_entries.require(id)
    crud.context_entries.delete(id)
    log_event(ctx, "context.deleted", "context", id, f"Contexte supprimé pour {_about(cur)} : « {cur['title']} »")
    return {"ok": True}
