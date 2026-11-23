"""Product categories: per company, defined by the data pack (seed/categories.json → meta.categories)."""

from app import crud
from app.core.db import get_meta

LEGACY = {
    "whole_fish": "Poisson entier", "fillet": "Filets et transformés", "shellfish": "Coquillages", "crustacean": "Crustacés",
    "frozen": "Surgelés", "produce": "Fruits et légumes", "dairy": "Crèmerie", "dry": "Épicerie",
}


def list_categories() -> list[dict]:
    """[{id, label}] from the pack; else derived from the products (legacy labels or the raw id)."""
    cats = get_meta().get("categories")
    if cats:
        return cats
    ids = dict.fromkeys(p["category"] for p in crud.products.all())
    return [{"id": c, "label": LEGACY.get(c, c)} for c in ids]


def category_map() -> dict[str, str]:
    return {c["id"]: c["label"] for c in list_categories()}


def category_label(id: str) -> str:
    return category_map().get(id, id)
