"""Loading the data pack (DATA_DIR/seed/*.json) into the database."""

from __future__ import annotations

import json
from pathlib import Path

from app import crud
from app.core.config import SEED_DIR
from app.core.db import Doc, freeze_heap, reset_sequences, set_meta, transaction

DEV_FIXTURE = Path(__file__).with_name("dev_fixture.json")


def read_pack() -> tuple[Doc, str]:
    """The data pack as {meta, products, clients, …} + where it came from.
    Falls back to a tiny built-in fixture when DATA_DIR/seed is missing."""
    if not (SEED_DIR / "meta.json").exists():
        return json.loads(DEV_FIXTURE.read_text("utf-8")), "dev-fixture (no DATA_DIR/seed found)"

    def read(key: str):
        f = SEED_DIR / f"{key}.json"
        return json.loads(f.read_text("utf-8")) if f.exists() else []

    pack: Doc = {"meta": read("meta")}
    if (SEED_DIR / "categories.json").exists():
        pack["meta"]["categories"] = read("categories")
    for key in crud.PACK:
        pack[key] = read(key)
    pack["contextEntries"] = [_context_entry(e) for e in pack["contextEntries"]]
    return pack, str(SEED_DIR)


def _context_entry(e: Doc) -> Doc:
    """Older data packs call `entityType` "scope": accept both."""
    if "entityType" in e or "scope" not in e:
        return e
    return {("entityType" if k == "scope" else k): v for k, v in e.items()}


def write_pack(pack: Doc) -> None:
    """Wipe everything and write a data pack."""
    with transaction():
        for key, table in crud.PACK.items():
            table.table.replace_all(pack.get(key) or [])
        crud.events.table.replace_all([])
        set_meta(pack["meta"])
    reset_sequences()
    freeze_heap()


def reset_from_pack() -> str:
    """Wipe the DB and reload the data pack. Returns the source."""
    pack, source = read_pack()
    write_pack(pack)
    return source


def counts() -> str:
    return ", ".join(f"{len(t.rows)} {k}" for k, t in crud.PACK.items())
