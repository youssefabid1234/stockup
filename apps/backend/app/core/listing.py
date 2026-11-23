"""Server-side pagination, sorting and the response shape shared by every list endpoint.

Every list route accepts:

    limit     rows to return (default 100, max 500)
    offset    rows to skip (default 0)
    sort      one of the route's sortable fields (unknown → the route's default order)
    order     asc | desc (default asc when `sort` is given; the default order has its own direction)
    envelope  1 → {"items", "total", "limit", "offset", …extras} instead of a plain array

Without `envelope` the response is a plain JSON array (the requested page): the AI tools and
scripts keep working unchanged. With `envelope=1` (what the web app sends) the response also says
how many rows match (`total`) and may carry list extras computed on the WHOLE filtered set, not just
the page: `counts` (rows per status/tab, ignoring the status/tab filter → tab badges), `sums`
(footer totals), `sumsByStatus`, `countsByType` (history), `countsBySource` (context), `facets` (filter options).

Services filter on the raw stored documents, sort with plain key functions, slice, and only then
build the (more expensive) summaries for the rows of the page.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Annotated, Any, Callable, Generic, Iterable, Literal, TypeVar

from fastapi import Depends, Query

from app.core.db import Doc
from app.core.utils import js_number, round2

LIMIT_DEFAULT = 100
LIMIT_MAX = 500

T = TypeVar("T")


@dataclass
class ListQuery:
    limit: int = LIMIT_DEFAULT
    offset: int = 0
    sort: str | None = None
    order: Literal["asc", "desc"] | None = None
    envelope: bool = False


def _int(value: str | None, default: int, lo: int, hi: int) -> int:
    n = js_number(value) if value not in (None, "") else math.nan
    return default if not math.isfinite(n) else max(lo, min(hi, math.floor(n)))


def list_query(
    limit: str | None = Query(None, description=f"Rows to return (default {LIMIT_DEFAULT}, max {LIMIT_MAX})"),
    offset: str | None = Query(None, description="Rows to skip (default 0)"),
    sort: str | None = Query(None, description="Sortable field of this list (see the route description)"),
    order: str | None = Query(None, description="asc | desc"),
    envelope: str | None = Query(None, description="1 → {items, total, limit, offset, …} instead of a plain array"),
) -> ListQuery:
    return ListQuery(
        limit=_int(limit, LIMIT_DEFAULT, 1, LIMIT_MAX),
        offset=_int(offset, 0, 0, 10**9),
        sort=sort or None,
        order="desc" if order == "desc" else "asc" if order == "asc" else None,
        envelope=envelope in ("1", "true"),
    )


ListDep = Annotated[ListQuery, Depends(list_query)]
"""Use in a list route: `def list_x(..., lq: ListDep)`."""


def legacy_limit(lq: ListQuery, default: int) -> ListQuery:
    """Routes that historically had a smaller default page (activity log: 50, search: 20)."""
    return lq if lq.limit != LIMIT_DEFAULT else ListQuery(default, lq.offset, lq.sort, lq.order, lq.envelope)


# ───────── Sorting ─────────

Key = Callable[[Any], Any]


def sort_rows(rows: list[T], key: Key, desc: bool = False) -> list[T]:
    """Stable sort by `key`; rows whose key is None (or "") always go last, whatever the direction."""
    present, missing = [], []
    for r in rows:
        (missing if key(r) in (None, "") else present).append(r)
    present.sort(key=key, reverse=desc)
    return present + missing


def apply_sort(rows: list[T], lq: ListQuery, keys: dict[str, Key], default: tuple[str, str] | None = None) -> list[T]:
    """Sort `rows` by `?sort=&order=` when `sort` names one of `keys`; else by `default` = (field, "asc"|"desc");
    `default=None` keeps the incoming order (already sorted by the service). Ties keep the incoming order."""
    if lq.sort in keys:
        return sort_rows(rows, keys[lq.sort], (lq.order or "asc") == "desc")
    if default:
        field, direction = default
        return sort_rows(rows, keys[field], direction == "desc")
    return rows


# ───────── Response ─────────


def respond(rows: list[Any], lq: ListQuery, view: Callable[[Any], Doc] | None = None,
            extras: Callable[[], Doc] | None = None) -> list[Doc] | Doc:  # fmt: skip
    """Slice the (filtered + sorted) rows to the requested page, build the views of the page only,
    and return a plain array or the envelope. `extras` is only computed for the envelope."""
    page = rows[lq.offset : lq.offset + lq.limit]
    items = [view(r) for r in page] if view else list(page)
    if not lq.envelope:
        return items
    out: Doc = {"items": items, "total": len(rows), "limit": lq.limit, "offset": lq.offset}
    if extras:
        out.update({k: v for k, v in extras().items() if v is not None})
    return out


def count_by(rows: Iterable[Any], field: Callable[[Any], str | None]) -> dict[str, int]:
    """{value: number of rows} (tab badges)."""
    out: dict[str, int] = {}
    for r in rows:
        k = field(r)
        if k is not None:
            out[k] = out.get(k, 0) + 1
    return out


def sum_of(rows: Iterable[Any], **fields: Callable[[Any], float]) -> dict[str, float]:
    """{name: Σ value} rounded to cents (footer totals)."""
    acc = {k: 0.0 for k in fields}
    for r in rows:
        for k, f in fields.items():
            acc[k] += f(r)
    return {k: round2(v) for k, v in acc.items()}


def sum_by(rows: Iterable[Any], group: Callable[[Any], str], **fields: Callable[[Any], float]) -> dict[str, dict[str, float]]:
    """{group: {name: Σ value}} (per-tab totals)."""
    acc: dict[str, dict[str, float]] = {}
    for r in rows:
        g = acc.setdefault(group(r), {k: 0.0 for k in fields})
        for k, f in fields.items():
            g[k] += f(r)
    return {g: {k: round2(v) for k, v in d.items()} for g, d in acc.items()}


def split_set(value: str | None) -> set[str] | None:
    """"a,b" → {"a", "b"}; empty → None."""
    out = {x.strip() for x in value.split(",") if x.strip()} if value else set()
    return out or None


# ───────── OpenAPI shape of the envelope ─────────

from app.schemas.base import Schema  # noqa: E402  (schemas import nothing from core.listing)


class Page(Schema, Generic[T]):
    """`?envelope=1` response of every list endpoint."""

    items: list[T]
    total: int
    limit: int
    offset: int
    counts: dict[str, int] | None = None
    sums: dict[str, float] | None = None
    sums_by_status: dict[str, dict[str, float]] | None = None
    counts_by_type: dict[str, int] | None = None
    counts_by_source: dict[str, int] | None = None
    facets: dict[str, list[str]] | None = None
