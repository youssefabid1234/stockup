"""Generic CRUD over one table of JSON documents.

Services never touch SQLite: they call `crud.orders.require(id)`, `crud.orders.put(doc)`, …
Documents are plain dicts with camelCase keys, shaped like the models in app/schemas/domain.py.
"""

from __future__ import annotations

import math
from typing import Callable, Iterable

from app.core.db import Doc, JsonTable, next_in_sequence
from app.core.errors import not_found
from app.core.utils import js_number


def _max_suffix(values: Iterable[str], prefix: str) -> int:
    """Highest numeric suffix among strings starting with `prefix` ("ord_000123" → 123)."""
    best = 0
    for v in values:
        if not v.startswith(prefix):
            continue
        n = js_number(v[len(prefix) :])
        if math.isfinite(n) and n > best:
            best = int(n)
    return best


class CRUDBase:
    """get / require (404) / all / filter / put (create or replace) / delete / next_id."""

    def __init__(self, table: JsonTable, label: str):
        self.table = table
        self.label = label  # French name used in 404 messages: "Commande introuvable : ord_1"

    @property
    def rows(self) -> dict[str, Doc]:
        return self.table.rows

    def get(self, key: str) -> Doc | None:
        return self.table.rows.get(key)

    def require(self, key: str) -> Doc:
        """Get or raise 404."""
        doc = self.table.rows.get(key)
        if doc is None:
            raise not_found(self.label, key)
        return doc

    def all(self) -> list[Doc]:
        return list(self.table.rows.values())

    def filter(self, predicate: Callable[[Doc], bool]) -> list[Doc]:
        return [d for d in self.table.rows.values() if predicate(d)]

    def put(self, doc: Doc) -> Doc:
        return self.table.put(doc)

    def delete(self, key: str) -> None:
        self.table.remove(key)

    def next_id(self, prefix: str, pad: int = 6) -> str:
        """Next id like "ord_000124", continuing after the highest existing one."""
        n = next_in_sequence(f"id:{self.table.name}:{prefix}", lambda: _max_suffix(self.table.rows.keys(), prefix))
        return f"{prefix}{n:0{pad}d}"


class NumberedCRUD(CRUDBase):
    """Documents that also carry a human number: CMD-2026-000123, ACH-…, FAC-…."""

    def next_number(self, kind: str, year: str) -> str:
        prefix = f"{kind}-{year}-"
        n = next_in_sequence(f"num:{prefix}", lambda: _max_suffix((d["number"] for d in self.table.rows.values()), prefix))
        return f"{prefix}{n:06d}"
