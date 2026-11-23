"""Global fuzzy search (accent/case-insensitive, token-based) — what the voice agent uses to turn
"c'est la poissonnerie Lemoine" or "le loup pour le bistrot" into a client id and a product id.

Query and fields are normalised (lowercase, no accents/punctuation), split into tokens, and French
fillers/stopwords are dropped ("bonjour c'est la …", "je voudrais … pour …"). Each candidate has a few
searchable fields with a weight; the best field wins. Field score = max of:
 - phrase match on the content tokens: exact 100 > prefix 90 > word prefix 80 > substring 65;
 - token match: each query token takes its best field token (exact > prefix > contains > typo-tolerant),
   score ≤ 85 from query coverage (most) + field coverage (how much of the name was said).
"""

from __future__ import annotations

import re

from app import crud
from app.core.db import Doc
from app.core.utils import cmp, fr_money, js_round, levenshtein, locale_cmp, normalize, sort_by
from app.services.context import entity_label

# Default types. "context" (context entries) is opt-in: pass types=context to include it.
ALL_TYPES = ["client", "product", "supplier", "order"]
MIN_SCORE = 35

# Fillers and stopwords never used to match (spoken French: greetings, articles, order verbs, units, days).
STOPWORDS = set(
    (
        "a au aux avec c ce ces cet cette d de des du en et est etes il elle j je l la le les leur m ma me mes moi mon "
        "n ne nous on ou par pas pour qu que qui s sa se ses son sur t ta te tes toi ton tu un une vous y "
        "c est cest ici voila oui non bon ben euh alors donc aussi encore svp stp merci bonjour bonsoir salut allo "
        "voudrais voudrait veux veut vouloir aimerais faudrait faut faire mettre mets mettez ajouter ajoute ajoutez "
        "commander commande prendre prends prenez avoir ai as avez peux pouvez pourriez please "
        "kg kilo kilos kilogramme kilogrammes g gr gramme grammes pce pces piece pieces douz douzaine douzaines litre litres "
        "demain aujourd hui ce soir matin apres midi"
    ).split(" ")
)
# Spoken/written abbreviations expanded before matching.
ABBREV = {"st": "saint", "ste": "sainte", "sts": "saints", "bd": "boulevard", "av": "avenue"}


def _tokens(s: str) -> list[str]:
    return [ABBREV.get(t, t) for t in normalize(s).split(" ") if t]


def _content(tokens: list[str]) -> list[str]:
    """Content tokens: no stopwords, no single letters, no bare numbers ("4 kg") — all tokens if nothing is left."""
    c = [t for t in tokens if len(t) > 1 and t not in STOPWORDS and not t.isdigit()]
    return c or tokens


def _word_sim(q: str, c: str) -> float:
    """Similarity 0..1 of one query token against one candidate token."""
    if c == q:
        return 1
    if c.startswith(q):
        return 0.95 if len(q) >= 2 else 0.5
    if len(q) < 3:
        return 0
    if len(q) >= 4 and q in c:
        return 0.8
    # Codes and numbers ("C0015", "n3") are never typo-matched: C0015 is not C0012.
    if re.search(r"\d", q) or re.search(r"\d", c):
        return 0
    # Compare to the whole word and to its prefix of the same length ("dorad" vs "daurade").
    d = min(levenshtein(q, c), levenshtein(q, c[: len(q)]))
    return max(0, 1 - d / max(len(q), 3))


TOKEN_MIN = 0.6


def score_field(qc: list[str], field: str) -> float:
    """Score query content tokens against one raw field (0..100)."""
    if not field or not qc:
        return 0
    fc = _content(_tokens(field))
    if not fc:
        return 0
    qs, fs = " ".join(qc), " ".join(fc)
    phrase = 0
    if fs == qs:
        phrase = 100
    elif fs.startswith(qs):
        phrase = 90
    elif f" {qs}" in fs:
        phrase = 80
    elif len(qs) >= 3 and qs in fs:
        phrase = 65

    q_sum = 0.0
    hit: set[int] = set()
    for qt in qc:
        best_sim, best_idx = 0.0, -1
        for i, ft in enumerate(fc):
            sim = _word_sim(qt, ft)
            if sim > best_sim:
                best_sim, best_idx = sim, i
        if best_sim >= TOKEN_MIN:
            q_sum += best_sim
            hit.add(best_idx)
    q_cov = q_sum / len(qc)
    f_cov = len(hit) / len(fc)
    tok = js_round(85 * (0.7 * q_cov + 0.3 * f_cov)) if hit else 0
    return max(phrase, tok)


def _best(qc: list[str], fields: list[tuple[str | None, float]]) -> int:
    s = 0.0
    for f, w in fields:
        if f:
            s = max(s, score_field(qc, f) * w)
    return js_round(s)


UNIT_SHORT = {"kg": "kg", "piece": "pce", "box": "colis", "dozen": "douz.", "liter": "L"}


def _price_label(price: float, unit: str) -> str:
    """"14,80 €/kg" (French formatting, shown as is in ⌘K and read by the agent)."""
    return f"{fr_money(price)} €/{UNIT_SHORT.get(unit, unit)}"


def search(raw_query: str, types: list[str] | None = None, limit: int = 20) -> list[Doc]:
    q = normalize(raw_query)
    if not q:
        return []
    qc = _content(_tokens(raw_query))
    want = set(types or ALL_TYPES)
    out: list[Doc] = []

    def push(r: Doc) -> None:
        if r["score"] >= MIN_SCORE:
            out.append(r)

    # Phone numbers only when the query looks like one (6+ digits), matched on the last 9 digits.
    phone = q.replace(" ", "")
    phone_q = [phone[-9:] if len(phone) > 9 else phone] if re.fullmatch(r"\d{6,}", phone) else None
    if "client" in want:
        for c in crud.clients.rows.values():
            fields = [(c["name"], 1), (c["code"], 1), (c["city"], 0.6), *((ct["name"], 0.85) for ct in c["contacts"])]
            phone_score = 0
            if phone_q:
                phones = [(re.sub(r"\D", "", ct["phone"])[-9:] if ct.get("phone") else None, 0.9) for ct in c["contacts"]]
                phone_score = _best(phone_q, phones)
            blocked = " · bloqué" if c["status"] == "blocked" else ""
            push({"type": "client", "id": c["id"], "label": c["name"], "sublabel": f"{c['code']} · {c['city']}{blocked}",
                  "score": max(_best(qc, fields), phone_score)})  # fmt: skip
    if "product" in want:
        for p in crud.products.rows.values():
            if not p["active"]:
                continue
            fields = [(p["name"], 1), (p["sku"], 1), *((a, 0.95) for a in p["aliases"])]
            push({"type": "product", "id": p["id"], "label": p["name"], "sublabel": f"{p['sku']} · {_price_label(p['price'], p['unit'])}",
                  "score": _best(qc, fields)})  # fmt: skip
    if "supplier" in want:
        for s in crud.suppliers.rows.values():
            fields = [(s["name"], 1), (s["city"], 0.6), *((ct["name"], 0.85) for ct in s["contacts"])]
            push({"type": "supplier", "id": s["id"], "label": s["name"], "sublabel": s["city"], "score": _best(qc, fields)})
    if "order" in want:
        for o in crud.orders.rows.values():
            # Orders are matched on their number only, never fuzzily ("123", "CMD-2026-000123").
            num = normalize(o["number"])
            if num == q:
                score = 100
            elif q.isdigit() and o["number"].endswith(q.rjust(6, "0")):
                score = 95
            elif len(q) >= 8 and num.startswith(q):
                score = 70
            else:
                continue
            client = crud.clients.get(o["clientId"])
            push({"type": "order", "id": o["id"], "label": o["number"],
                  "sublabel": f"{client['name'] if client else '?'} · {o['deliveryDate']} · {o['status']}", "score": score})  # fmt: skip
    if "context" in want:
        for e in crud.context_entries.rows.values():
            fields = [(e["title"], 1), (" ".join(e.get("tags") or []), 0.8), (e["body"], 0.6)]
            about = entity_label(e["entityType"], e.get("entityId")) or e.get("entityId") or ""
            push({"type": "context", "id": e["id"], "label": e["title"], "sublabel": f"{about} · {e['kind']}", "score": _best(qc, fields)})
    return sort_by(out, lambda a, b: cmp(b["score"], a["score"]) or locale_cmp(a["label"], b["label"]))[:limit]
