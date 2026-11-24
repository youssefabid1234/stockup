"""
Team 12 (Youssef, rule by Daycem) · demo data that must survive every ERP reset.

Real life: while the AOP tourage is out, the wholesaler runs a short promotion on the standard 82 % tourage, aimed at
the bakeries who used to buy the AOP one and accept a substitute (Daycem, T4). FICTIONAL demo data (DECISIONS.md §5).
data/seed/ is not in git and every reset (web button, `make reset`, `run_scenarios.py --reset`) reloads it, which used
to erase the rule created by scripts/setup_demo_data.py. Here it is added to the pack itself, each time the pack is
read, so the jury gets it after `make setup` with nothing else to run.

Same tag, targets and rule as scripts/setup_demo_data.py (tests/test_setup_demo_data.py checks it): the tag
« promo-tourage » on a FROZEN list of 6 bakeries (computed by scripts/promo_target.py), and one rule on that tag ×
Beurre de tourage 82 % (prd_0026), −8 % on the list price, from the business date to the end of that month.
Skipped if the pack lacks the product or every target client (another company's pack); never added twice.
"""

from __future__ import annotations

import calendar
from datetime import date

from .db import Doc

PRODUCT_ID = "prd_0026"  # Beurre de tourage 82 % (plaque 2 kg)
PROMO_TAG = "promo-tourage"
DISCOUNT_PCT = 8.0
# Frozen list (DECISIONS §5), the same as scripts/setup_demo_data.py: bakeries with ≥ 2 orders of AOP tourage over
# 12 months that accept a substitute (scripts/promo_target.py).
TARGET_CLIENT_IDS = ["cli_0020", "cli_0033", "cli_0060", "cli_0070", "cli_0085", "cli_0102"]
RULE_ID = "prl_0900"  # far from the seed's ids; new rules created in the ERP continue after it
# Epiphany articles the data pack ships inactive while the company docs (01-entreprise.md) say pre-orders are open
# until 15/12 and clients have pre-orders in their cards: the agent refused them in 3 of 150 test calls (24/11).
ACTIVATE = ("prd_0068", "prd_0069")  # couronnes des rois, fèves des rois


def english() -> bool:
    """The English data pack is loaded (SEED_DIR_NAME=seed_en): name the rule in English too."""
    from .config import SEED_DIR

    return SEED_DIR.name.endswith("_en")


def demo_tag() -> Doc:
    if english():
        return {"id": PROMO_TAG, "scope": "client", "label": "Laminating butter promo (demo)", "color": "amber",
                "description": "Demo data: bakeries that used to buy the AOP laminating butter and accept a substitute."}  # fmt: skip
    return {"id": PROMO_TAG, "scope": "client", "label": "Promo tourage (démo)", "color": "amber",
            "description": "Données de démo : boulangeries qui achetaient le tourage AOP et acceptent un remplaçant."}  # fmt: skip


def demo_price_rule(today: date) -> Doc:
    end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return {
        "id": RULE_ID,
        "name": (f"Promo 82% laminating butter: −{DISCOUNT_PCT:g}% until {end:%d/%m}" if english()
                 else f"Promo tourage 82 % : −{DISCOUNT_PCT:g} % jusqu'au {end:%d/%m}"),
        "active": True,
        "priority": 0,
        "clientScope": {"kind": "tag", "tag": PROMO_TAG},
        "productScope": {"kind": "product", "productId": PRODUCT_ID},
        "method": {"kind": "discount_pct", "pct": DISCOUNT_PCT},
        "validFrom": today.isoformat(),
        "validTo": end.isoformat(),
        "note": ("Demo data (hackathon): clearing standard laminating butter while the AOP one is out of stock, aimed at "
                 "the bakeries that used to buy the AOP one and accept a substitute." if english()
                 else "Données de démo (hackathon) : déstockage du tourage standard pendant la rupture du tourage AOP, "
                 "ciblé sur les boulangeries qui achetaient l'AOP et acceptent un remplaçant."),
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
    targets = [c for c in pack.get("clients") or [] if c.get("id") in TARGET_CLIENT_IDS]
    if PRODUCT_ID not in products or not targets:
        return added
    tags = pack.setdefault("tags", [])
    if not any(t.get("id") == PROMO_TAG and t.get("scope", "client") == "client" for t in tags if isinstance(t, dict)):
        tags.append(demo_tag())
        added.append(f"tag {PROMO_TAG}")
    for c in targets:  # the tag on the targets, their other tags kept, never twice
        if PROMO_TAG not in (c.get("tags") or []):
            c["tags"] = [*(c.get("tags") or []), PROMO_TAG]
    rule = demo_price_rule(date.fromisoformat(str(today_raw)[:10]))
    rules = pack.setdefault("priceRules", [])
    if not any(r.get("id") == rule["id"] or r.get("name") == rule["name"] for r in rules):
        rules.append(rule)
        added.append(rule["name"])
    return added
