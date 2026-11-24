"""Groups (tags) for clients, suppliers and products. A TagDef defines a group; entities carry tag ids
in their `tags` array. Price rules can target a client group or a product group (see pricing.py).
Also: the PATCH of products and suppliers (price, cost, tags, …)."""

from __future__ import annotations

from app import crud
from app.core.activity import Ctx, log_event
from app.core.db import Doc, transactional
from app.core.errors import bad_request, conflict, not_found
from app.core.utils import fmt_eur, locale_cmp, sort_by

SCOPE_FR = {"client": "clients", "supplier": "fournisseurs", "product": "produits"}


def _entities_of(scope: str) -> list[Doc]:
    if scope == "client":
        return crud.clients.all()
    return crud.suppliers.all() if scope == "supplier" else crud.products.all()


def list_tags(scope: str | None = None) -> list[Doc]:
    """Tag defs with usage counts. Tags used on entities but never defined are listed too (label = id)."""
    out: list[Doc] = []
    for s in [scope] if scope else ["client", "supplier", "product"]:
        counts: dict[str, int] = {}
        for e in _entities_of(s):
            for t in e.get("tags") or []:
                counts[t] = counts.get(t, 0) + 1
        defs = crud.tags.filter(lambda t: t["scope"] == s)
        out += [{**d, "count": counts.get(d["id"], 0)} for d in defs]
        out += [{"id": t, "scope": s, "label": t, "count": n} for t, n in counts.items() if not any(d["id"] == t for d in defs)]
    return sort_by(out, lambda a, b: locale_cmp(a["scope"], b["scope"]) or locale_cmp(a["label"], b["label"]))


def tag_label(scope: str, id: str) -> str:
    tag = crud.tags.get(f"{scope}|{id}")
    return tag["label"] if tag else id


def check_tags(scope: str, tags: list[str] | None, existing: list[str] | None = None) -> None:
    """400 if a tag is not defined for that scope (tags already on the entity are tolerated)."""
    for t in tags or []:
        if t not in (existing or []) and not crud.tags.get(f"{scope}|{t}"):
            raise bad_request("unknown_tag", f"Groupe inconnu ({scope}) : {t}")


@transactional
def create_tag(ctx: Ctx, tag: Doc) -> Doc:
    if crud.tags.get(f"{tag['scope']}|{tag['id']}"):
        raise conflict("tag_exists", f"Le groupe {tag['id']} existe déjà")
    crud.tags.put(tag)
    log_event(ctx, "tag.created", tag["scope"], tag["id"], f"Nouveau groupe de {SCOPE_FR[tag['scope']]} : {tag['label']}")
    return tag


@transactional
def update_tag(ctx: Ctx, scope: str, id: str, patch: Doc) -> Doc:
    tag = crud.tags.get(f"{scope}|{id}")
    if not tag:
        raise not_found("Groupe", f"{scope}/{id}")
    updated = crud.tags.put({**tag, **patch})
    log_event(ctx, "tag.updated", scope, id, f"Groupe de {SCOPE_FR[scope]} « {updated['label']} » modifié")
    return updated


@transactional
def delete_tag(ctx: Ctx, scope: str, id: str) -> Doc:
    """Delete a tag def and remove it from every entity of that scope. Rules targeting it stop matching."""
    tag = crud.tags.get(f"{scope}|{id}")
    if not tag:
        raise not_found("Groupe", f"{scope}/{id}")
    crud.tags.delete(f"{scope}|{id}")
    table = {"client": crud.clients, "supplier": crud.suppliers, "product": crud.products}[scope]
    for e in table.all():
        if id in (e.get("tags") or []):
            table.put({**e, "tags": [t for t in e["tags"] if t != id]})
    log_event(ctx, "tag.deleted", scope, id, f"Groupe de {SCOPE_FR[scope]} « {tag['label']} » supprimé")
    return {"ok": True}


def _labels(scope: str, tags: list[str]) -> str:
    return ", ".join(tag_label(scope, t) for t in tags) or "aucun"


@transactional
def update_product(ctx: Ctx, id: str, patch: Doc) -> Doc:
    p = crud.products.require(id)
    check_tags("product", patch.get("tags"), p.get("tags"))
    updated = crud.products.put({**p, **patch})
    summary = f"Produit {p['name']} modifié ({', '.join(patch)})"
    if "price" in patch and patch["price"] != p["price"]:
        summary = f"Prix catalogue de {p['name']} : {fmt_eur(p['price'])} → {fmt_eur(patch['price'])}"
    elif "tags" in patch:
        summary = f"Groupes de {p['name']} : {_labels('product', patch['tags'])}"
    log_event(ctx, "product.price_changed" if "price" in patch else "product.updated", "product", id, summary)
    return updated


@transactional
def update_supplier(ctx: Ctx, id: str, patch: Doc) -> Doc:
    s = crud.suppliers.require(id)
    check_tags("supplier", patch.get("tags"), s.get("tags"))
    updated = crud.suppliers.put({**s, **patch})
    if "tags" in patch:
        summary = f"Groupes du fournisseur {s['name']} : {_labels('supplier', patch['tags'])}"
    else:
        summary = f"Fournisseur {s['name']} modifié ({', '.join(patch)})"
    log_event(ctx, "supplier.updated", "supplier", id, summary)
    return updated


