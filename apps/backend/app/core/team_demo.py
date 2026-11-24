"""
Team 12 (Youssef, rule by Daycem) · demo data that must survive every ERP reset.

Real life: while the AOP tourage is out, the wholesaler runs a short promotion on the standard 82 % tourage for its
bakeries. That rule is FICTIONAL demo data (DECISIONS.md §5). data/seed/ is not in git and every reset (web button,
`make reset`, `run_scenarios.py --reset`) reloads it, which used to erase the rule created by
scripts/setup_demo_data.py. Here it is added to the pack itself, each time the pack is read, so the jury gets it
after `make setup` with nothing else to run.

Same rule as scripts/setup_demo_data.py (same name, so that script says « déjà là »): group « Boulangeries » ×
Beurre de tourage 82 % (prd_0026), −8 % on the list price, from the business date to the end of that month.
Skipped if the pack lacks the product or the tag (another company's pack), or if the rule is already there.
"""

from __future__ import annotations

import calendar
from datetime import date

from .db import Doc

PRODUCT_ID = "prd_0026"  # Beurre de tourage 82 % (plaque 2 kg)
CLIENT_TAG = "boulangeries"
DISCOUNT_PCT = 8.0
RULE_ID = "prl_0900"
# Epiphany articles the data pack ships inactive while the company docs (01-entreprise.md) say pre-orders are open
# until 15/12 and clients have pre-orders in their cards: the agent refused them in 3 of 150 test calls (24/11).
ACTIVATE = ("prd_0068", "prd_0069")  # couronnes des rois, fèves des rois


def english() -> bool:
    """The English data pack is loaded (SEED_DIR_NAME=seed_en): name the rule in English too."""
    from .config import SEED_DIR

    return SEED_DIR.name.endswith("_en")


def demo_price_rule(today: date) -> Doc:
    end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return {
        "id": RULE_ID,
        "name": (f"Promo 82% laminating butter: −{DISCOUNT_PCT:g}% until {end:%d/%m}" if english()
                 else f"Promo tourage 82 % : −{DISCOUNT_PCT:g} % jusqu'au {end:%d/%m}"),
        "active": True,
        "priority": 0,
        "clientScope": {"kind": "tag", "tag": CLIENT_TAG},
        "productScope": {"kind": "product", "productId": PRODUCT_ID},
        "method": {"kind": "discount_pct", "pct": DISCOUNT_PCT},
        "validFrom": today.isoformat(),
        "validTo": end.isoformat(),
        "note": ("Demo data (hackathon): clearing standard laminating butter while the AOP one is out of stock." if english()
                 else "Données de démo (hackathon) : déstockage du tourage standard pendant la rupture du tourage AOP."),
        "createdAt": f"{today.isoformat()}T06:00:00.000Z",
    }


def add_team_demo_data(pack: Doc) -> list[str]:
    """Add the demo rows to a pack read from DATA_DIR/seed (in place). Returns what was added (for the log)."""
    added: list[str] = []
    for p in pack.get("products") or []:
        if p.get("id") in ACTIVATE and not p.get("active", True):
            p["active"] = True
            added.append(f"{p['id']} actif")
    today_raw = (pack.get("meta") or {}).get("today")
    if not today_raw:
        return added
    products = {p.get("id") for p in pack.get("products") or []}
    tags = {t.get("id") or t.get("slug") or t.get("name") for t in pack.get("tags") or [] if isinstance(t, dict)}
    clients_tagged = any(CLIENT_TAG in (c.get("tags") or []) for c in pack.get("clients") or [])
    if PRODUCT_ID not in products or not (CLIENT_TAG in tags or clients_tagged):
        return added
    rule = demo_price_rule(date.fromisoformat(str(today_raw)[:10]))
    rules = pack.setdefault("priceRules", [])
    if any(r.get("id") == rule["id"] or r.get("name") == rule["name"] for r in rules):
        return added
    rules.append(rule)
    return [*added, rule["name"]]
