"""
Team 12 (Youssef) · translate the ERP data pack (data/seed, French) into English → data/seed_en.

Why: the agent is moving to English; the ERP data it reads (products, client cards, history, context notes) must be
English too. data/seed is not in git (the team zip ships it); data/seed_en IS committed, so everyone (and the jury,
after `make setup`) gets the English ERP. The backend reads it when SEED_DIR_NAME=seed_en (apps/backend core/config).

What is translated / kept (see FIELDS below):
  - translated: product names, aliases, packaging, categories, tags, client preferences and notes, contact roles,
    history (client & supplier events), context notes, order / stock / route notes, price-rule names;
  - kept as is: ids, numbers, amounts, dates, codes (status, type, slugs like "beurres"), business and people names,
    addresses, cities, bank references, order / invoice numbers;
  - invoice lines « <product> (BL 001963 du 22/03) » → « <product in English> (DN 001963 of 22/03) », no model.

How: unique strings only, in batches (JSON array in → JSON array out, same length), in parallel, with the team's
LLM key (LLM_* in .env, never printed). Step 1 translates the catalogue (products, categories, tags) and makes a
glossary; step 2 sends that glossary with every batch so product names stay identical everywhere. Every
translation is cached (--cache) so a rerun only translates what is missing. A batch that fails twice keeps French.

    cd apps/ai && .venv/bin/python ../../scripts/translate_seed.py            # all
    .venv/bin/python ../../scripts/translate_seed.py --dry-run                # counts only, no model call
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/ai"))

SRC, DST = ROOT / "data/seed", ROOT / "data/seed_en"
CODE = re.compile(r"^[a-z0-9]+([_-][a-z0-9]+)*$")  # slugs / enum values ("beurres", "price_negotiation"): never touched

# file → fields to translate (dotted path inside one record; lists are walked)
FIELDS: dict[str, set[str]] = {
    "products": {"name", "aliases", "caliber"},
    "categories": {"label"},
    "tags": {"label", "description"},
    "clients": {"preferences", "notes.text", "contacts.role", "contacts.name"},
    "suppliers": {"notes", "contacts.role", "contacts.name"},
    "clientEvents": {"title", "description", "resolution"},
    "supplierEvents": {"title", "description", "resolution"},
    "contextEntries": {"title", "body"},
    "orders": {"note", "lines.note"},
    "purchaseOrders": {"note"},
    "stockMovements": {"note"},
    "routeRuns": {"stops.note"},
    "routes": {"name", "vehicle"},
    "priceRules": {"name", "note"},
}
CATALOGUE = {"products", "categories", "tags"}
INVOICE_LINE = re.compile(r"^(?P<name>.*) \(BL (?P<num>\d+) du (?P<day>\d\d/\d\d)\)$")

SYSTEM = """You translate the data of a French bakery-supplies wholesaler's ERP (Le Fournil Occitan, Toulouse) into natural, professional British English.
Input: a JSON array of French strings. Output: ONLY a JSON array of the English translations, same length, same order, nothing else.
Rules:
- Keep unchanged: business names (« Maison Sarrailh », « Le Pétrin de Colomiers »), people's first and last names, place names, addresses, product codes and ids (prd_0025, CMD-2026-003828, FAC-…), numbers, amounts, percentages, dates and times.
- A contact « name » that is a department or role (« Comptabilité fournisseurs ») is translated; a person's name is kept.
- Trade words: tourage → laminating butter (« plaque » → sheet), tradi / farine de tradition → traditional (French) flour, viennoiserie → viennoiserie, galette des rois → galette des rois, BL → DN (delivery note), franco → free-delivery threshold, avoir → credit note.
- Translate EVERYTHING else, including quoted speech in « » (write it as “…” in English) and short spoken phrases.
- Keep the tone and length; keep markdown, lists and line breaks exactly.
- Product names must match the glossary below exactly whenever a product is mentioned."""


def walk(rec, path: list[str], want: str):
    """Yield (container, key) for every string at dotted path `want` inside a record (lists are walked)."""
    head, _, rest = want.partition(".")
    if isinstance(rec, list):
        for x in rec:
            yield from walk(x, path, want)
        return
    if not isinstance(rec, dict) or head not in rec:
        return
    val = rec[head]
    if rest:
        yield from walk(val, path + [head], rest)
    elif isinstance(val, list):
        for i, x in enumerate(val):
            if isinstance(x, str):
                yield val, i
    elif isinstance(val, str):
        yield rec, head


def translatable(s: str) -> bool:
    s = s.strip()
    return bool(s) and not CODE.match(s) and bool(re.search(r"[A-Za-zÀ-ÿ]{2}", s))


def load(name: str):
    return json.loads((SRC / f"{name}.json").read_text(encoding="utf-8"))


def collect(files: dict[str, object], names) -> list[str]:
    seen: dict[str, None] = {}
    for name in names:
        for f in FIELDS.get(name, ()):
            for rec in files[name]:
                for box, key in walk(rec, [], f):
                    if translatable(box[key]):
                        seen.setdefault(box[key].strip(), None)
    return list(seen)


def batches(strings: list[str], max_chars: int, max_items: int):
    cur, size = [], 0
    for s in strings:
        if cur and (size + len(s) > max_chars or len(cur) >= max_items):
            yield cur
            cur, size = [], 0
        cur.append(s)
        size += len(s)
    if cur:
        yield cur


async def translate_batch(llm, system: str, items: list[str]) -> list[str] | None:
    from app.clients.base import LLMRequest, LLMText
    from app.schemas import ChatMessage

    req = LLMRequest(system=system, messages=[ChatMessage(role="user", content=json.dumps(items, ensure_ascii=False))],
                     max_tokens=16000)  # fmt: skip
    text = "".join([ev.delta async for ev in llm.stream(req) if isinstance(ev, LLMText)])
    start, end = text.find("["), text.rfind("]")
    try:
        out = json.loads(text[start : end + 1])
    except (ValueError, TypeError):
        return None
    if not isinstance(out, list) or len(out) != len(items) or not all(isinstance(x, str) for x in out):
        return None
    return out


async def translate_all(llm, system, strings, cache, label, max_chars, workers):
    todo = [s for s in strings if s not in cache]
    print(f"[{label}] {len(strings)} unique strings, {len(todo)} to translate ({sum(map(len, todo))} chars)", flush=True)
    sem = asyncio.Semaphore(workers)
    done = 0
    failed: list[str] = []
    t0 = time.monotonic()

    async def run(items: list[str], depth=0):
        nonlocal done
        async with sem:
            try:
                out = await translate_batch(llm, system, items)
            except Exception as e:  # network / rate limit: retry smaller
                print(f"  ! batch of {len(items)}: {type(e).__name__}", flush=True)
                out = None
        if out is None:
            if len(items) > 1 and depth < 3:
                mid = len(items) // 2
                await asyncio.gather(run(items[:mid], depth + 1), run(items[mid:], depth + 1))
                return
            failed.extend(items)
            return
        cache.update(zip(items, out))
        done += len(items)
        if done % 200 < len(items):
            print(f"  {done}/{len(todo)} · {time.monotonic() - t0:.0f}s", flush=True)

    await asyncio.gather(*(run(b) for b in batches(todo, max_chars, 60)))
    print(f"[{label}] done in {time.monotonic() - t0:.0f}s · kept in French (failed): {len(failed)}", flush=True)
    return failed


def apply(files, cache, glossary):
    """Write the translations into the records (in place). Returns {file: replaced count}."""
    counts = {}
    for name, fields in FIELDS.items():
        n = 0
        for f in fields:
            for rec in files[name]:
                for box, key in walk(rec, [], f):
                    s = box[key].strip()
                    if s in cache:
                        box[key] = cache[s]
                        n += 1
        counts[name] = n
    n = 0
    for inv in files["invoices"]:
        for line in inv.get("lines") or []:
            lab = line.get("label") or ""
            m = INVOICE_LINE.match(lab)
            name = m.group("name") if m else lab
            en = glossary.get(name) or cache.get(name)
            if en:
                line["label"] = f"{en} (DN {m.group('num')} of {m.group('day')})" if m else en
                n += 1
    counts["invoices"] = n
    return counts


async def main(args) -> int:
    from app.clients.factory import make_llm_client
    from app.config import settings

    names = sorted(p.stem for p in SRC.glob("*.json"))
    files = {n: load(n) for n in names}
    cache_path = Path(args.cache)
    cache: dict[str, str] = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}

    catalogue = collect(files, sorted(CATALOGUE))
    rest = [s for s in collect(files, sorted(set(FIELDS) - CATALOGUE)) if s not in set(catalogue)]
    print(f"catalogue: {len(catalogue)} strings · rest: {len(rest)} strings, {sum(map(len, rest))} chars · cached: {len(cache)}")
    if args.dry_run:
        return 0

    glossary_llm = make_llm_client(replace(settings.llm, model=args.glossary_model))
    bulk_llm = make_llm_client(replace(settings.llm, model=args.model))
    try:
        failed = await translate_all(glossary_llm, SYSTEM, catalogue, cache, "catalogue", 3000, args.workers)
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
        products = {p["name"]: cache.get(p["name"].strip(), p["name"]) for p in files["products"]}
        gloss = "\n".join(f"- {fr} → {en}" for fr, en in products.items())
        system = f"{SYSTEM}\n\nProduct glossary (French → English):\n{gloss}"
        failed += await translate_all(bulk_llm, system, rest, cache, "rest", args.max_chars, args.workers)
    finally:
        cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")

    counts = apply(files, cache, products)
    DST.mkdir(exist_ok=True)
    for name, data in files.items():
        (DST / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    (DST / "GLOSSARY.md").write_text(
        "# Product names, French → English (generated by scripts/translate_seed.py)\n\n"
        + "\n".join(f"| `{p['id']}` | {p['name']} | {products[p['name']]} |" for p in load("products"))
        + "\n",
        encoding="utf-8",
    )
    print("written:", {k: v for k, v in counts.items() if v}, "· still French:", len(failed))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--model", default="claude-haiku-5-5", help="bulk text (history, notes)")
    ap.add_argument("--glossary-model", default="claude-sonnet-5-5", help="catalogue: product names, categories, tags")
    ap.add_argument("--cache", default=str(ROOT / "data/seed_en.cache.json"))
    ap.add_argument("--max-chars", type=int, default=6000)
    ap.add_argument("--workers", type=int, default=8)
    sys.exit(asyncio.run(main(ap.parse_args())))
