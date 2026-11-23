"""Storage: SQLite tables of JSON documents, mirrored in memory.

Every entity lives in its own table as a JSON document: (id TEXT PRIMARY KEY, data TEXT).
The dataset is small, so on boot every table is loaded into memory (a dict per table) and all
reads hit memory. Writes go to memory AND to SQLite immediately (write-through).

Wrap any multi-step write in `@transactional` (or `with transaction():`): it runs inside one
SQLite transaction and, if anything raises, rolls back AND reloads memory from disk so the two
never drift apart.
"""

from __future__ import annotations

import gc
import json
import sqlite3
from contextlib import contextmanager
from functools import wraps
from typing import Any, Callable, Iterator

from app.core.config import DB_PATH

Doc = dict[str, Any]
"""A stored document: the JSON object exactly as the API returns it (camelCase keys)."""

DB_PATH.parent.mkdir(parents=True, exist_ok=True)
# isolation_level=None: we open/close transactions ourselves (BEGIN / COMMIT / ROLLBACK).
conn = sqlite3.connect(DB_PATH, isolation_level=None, check_same_thread=False)
conn.execute("PRAGMA journal_mode = WAL")
conn.execute("PRAGMA synchronous = NORMAL")


# Data version: bumped on every write / reload. Derived views (stock levels, client aggregates, sorted
# indexes…) are cached per version with @per_data_version and rebuilt lazily after a change.
_version = 0


def data_version() -> int:
    return _version


def _bump() -> None:
    global _version
    _version += 1


def per_data_version(fn: Callable[[], Any]) -> Callable[[], Any]:
    """Cache a no-argument derived view until the next write. The cached value is SHARED: never mutate it."""
    cache: dict[str, Any] = {}

    @wraps(fn)
    def wrapper() -> Any:
        if cache.get("v") != _version:
            cache["value"] = fn()
            cache["v"] = _version
        return cache["value"]

    return wrapper


def _dumps(doc: Doc) -> str:
    return json.dumps(doc, ensure_ascii=False, separators=(",", ":"))


class JsonTable:
    """One SQLite table of JSON documents + its in-memory copy (`rows`, insertion-ordered)."""

    def __init__(self, name: str, key_of: Callable[[Doc], str] = lambda d: d["id"]):
        self.name = name
        self.key_of = key_of
        self.rows: dict[str, Doc] = {}
        conn.execute(f"CREATE TABLE IF NOT EXISTS {name} (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
        ALL_TABLES.append(self)

    def put(self, doc: Doc) -> Doc:
        key = self.key_of(doc)
        self.rows[key] = doc
        _bump()
        conn.execute(
            f"INSERT INTO {self.name} (id, data) VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET data = excluded.data",
            (key, _dumps(doc)),
        )
        return doc

    def remove(self, key: str) -> None:
        self.rows.pop(key, None)
        _bump()
        conn.execute(f"DELETE FROM {self.name} WHERE id = ?", (key,))

    def load(self) -> None:
        """Reload the memory copy from SQLite."""
        self.rows = {r[0]: json.loads(r[1]) for r in conn.execute(f"SELECT id, data FROM {self.name} ORDER BY rowid")}
        _bump()

    def replace_all(self, docs: list[Doc]) -> None:
        """Replace the whole table content (seed / reset)."""
        conn.execute(f"DELETE FROM {self.name}")
        self.rows = {}
        _bump()
        for d in docs:
            self.put(d)


ALL_TABLES: list[JsonTable] = []

# ───────── Meta (key/value): the data pack's meta.json ─────────

conn.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
_meta_cache: Doc | None = None


def get_meta() -> Doc:
    global _meta_cache
    if _meta_cache is None:
        row = conn.execute("SELECT value FROM meta WHERE key = 'meta'").fetchone()
        if not row:
            raise RuntimeError("Database not seeded (no meta row)")
        _meta_cache = json.loads(row[0])
    return _meta_cache


def set_meta(meta: Doc) -> None:
    global _meta_cache
    _bump()
    conn.execute(
        "INSERT INTO meta (key, value) VALUES ('meta', ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (_dumps(meta),),
    )
    _meta_cache = meta


def is_seeded() -> bool:
    return conn.execute("SELECT 1 FROM meta WHERE key = 'meta'").fetchone() is not None


def load_all() -> None:
    """Reload every table from SQLite (boot, or after a rollback)."""
    global _meta_cache
    for t in ALL_TABLES:
        t.load()
    _meta_cache = None
    reset_sequences()
    freeze_heap()


def freeze_heap() -> None:
    """Move the loaded documents (millions of objects with the big data packs) out of the cyclic GC's reach:
    otherwise every full collection rescans them and a request can stall for a few hundred ms."""
    gc.collect()
    gc.freeze()


# ───────── Transactions ─────────

_depth = 0
_after_commit: list[Callable[[], None]] = []


@contextmanager
def transaction() -> Iterator[None]:
    """Run a block atomically. Nested blocks join the outermost transaction."""
    global _depth
    if _depth == 0:
        conn.execute("BEGIN")
    _depth += 1
    try:
        yield
    except BaseException:
        _depth -= 1
        if _depth == 0:
            conn.execute("ROLLBACK")
            _after_commit.clear()
            load_all()  # SQLite rolled back; bring memory back in line
        raise
    _depth -= 1
    if _depth == 0:
        conn.execute("COMMIT")
        callbacks = list(_after_commit)
        _after_commit.clear()
        for cb in callbacks:
            cb()


def transactional(fn: Callable) -> Callable:
    """Decorator: the whole function runs in one transaction (all or nothing)."""

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        with transaction():
            return fn(*args, **kwargs)

    return wrapper


def on_commit(cb: Callable[[], None]) -> None:
    """Run `cb` once the current transaction commits (immediately if none is open)."""
    if _depth == 0:
        cb()
    else:
        _after_commit.append(cb)


# ───────── Id / document number sequences ─────────

_seqs: dict[str, int] = {}


def reset_sequences() -> None:
    _seqs.clear()


def next_in_sequence(key: str, current_max: Callable[[], int]) -> int:
    """Next value of a named counter, starting after `current_max()` the first time."""
    n = _seqs.get(key)
    if n is None:
        n = current_max()
    n += 1
    _seqs[key] = n
    return n
