"""
Team 12 · Demo data that cannot live in git (data/seed/ is git-ignored). OWNER: Daycem (T4).

Real life: while the AOP tourage is out, the wholesaler runs a short promotion on the standard 82 % tourage to move
stock, aimed at the bakeries who USED TO BUY the AOP one and accept a substitute (they are the ones who would switch).
Before (24/11), it went to every « boulangeries » client: a windfall for the 29 who buy the 82 % anyway, and given to
13 who refuse any substitute. FICTIONAL demo data, written in DECISIONS.md §5.

    Target: clients of « boulangeries », active, ≥ 2 orders of the AOP tourage (prd_0025) over the last 12 months,
            whose card does not refuse substitutes (« demander » kept: the agent still asks first).
            FROZEN list below, computed by scripts/promo_target.py (tests/test_promo_target.py says if the data moved).
    Tag:    « promo-tourage » set on those clients (their other tags kept); one rule on that tag.
    Rule:   tag « promo-tourage » × Beurre de tourage 82 % (prd_0026), −8 % on the list price, from the ERP business
            date (GET /api/meta → today) to the end of that month. A negotiated price always wins.
    Effect: 9,20 € → 8,46 €/kg for the 6 targets; 9,20 € for the other bakeries (negotiated prices unchanged).

Since PR #25, apps/backend/app/core/team_demo.py (Youssef) adds the same tag, targets and rule to the data pack at every
reset; tests/test_setup_demo_data.py checks both build exactly the same thing. This script stays for an ERP that was
not reset (or edited by hand): idempotent, it creates or fixes what is missing and never duplicates. `--check` reads.

    python scripts/setup_demo_data.py            # host (needs httpx), ERP on http://localhost:4000
    docker compose cp scripts/setup_demo_data.py ai:/tmp/ && \\
      docker compose exec -e ERP_URL=http://backend:4000 ai python /tmp/setup_demo_data.py
"""

import argparse
import calendar
import os
import sys
from datetime import date

import httpx

ERP = os.environ.get("ERP_URL", "http://localhost:4000")
PRODUCT_ID = "prd_0026"  # Beurre de tourage 82 % (plaque 2 kg): the substitute on promotion
OUT_OF_STOCK_PRODUCT_ID = "prd_0025"  # Beurre de tourage AOP Charentes-Poitou 84 %: the product it replaces
CLIENT_GROUP = "boulangeries"  # where the target was looked for
PROMO_TAG = "promo-tourage"
DISCOUNT_PCT = 8.0
# Frozen (DECISIONS §5): scripts/promo_target.py --tag boulangeries --product prd_0025 --min-orders 2 --months 12
# = Boulangerie-Pâtisserie Rémy, Au Fournil de Sandrine, La Mie de Saint-Michel, Au Pain de Guilhem,
#   La Mie d'Arnaud-Bernard, Au Fournil de Guillaume. Same list in apps/backend/app/core/team_demo.py.
TARGET_CLIENT_IDS = ["cli_0020", "cli_0033", "cli_0060", "cli_0070", "cli_0085", "cli_0102"]


def build_demo_tag() -> dict:
    """The TagInput sent to POST /api/tags (pure: tested without the ERP)."""
    return {
        "id": PROMO_TAG,
        "scope": "client",
        "label": "Promo tourage (démo)",
        "color": "amber",
        "description": "Données de démo : boulangeries qui achetaient le tourage AOP et acceptent un remplaçant.",
    }


def build_demo_rule(today: date) -> dict:
    """The PriceRuleInput sent to POST /api/price-rules (pure: tested without the ERP)."""
    end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return {
        "name": f"Promo tourage 82 % : −{DISCOUNT_PCT:g} % jusqu'au {end:%d/%m}",
        "active": True,
        "priority": 0,
        "clientScope": {"kind": "tag", "tag": PROMO_TAG},
        "productScope": {"kind": "product", "productId": PRODUCT_ID},
        "method": {"kind": "discount_pct", "pct": DISCOUNT_PCT},
        "validFrom": today.isoformat(),
        "validTo": end.isoformat(),
        "note": ("Données de démo (hackathon) : déstockage du tourage standard pendant la rupture du tourage AOP, "
                 "ciblé sur les boulangeries qui achetaient l'AOP et acceptent un remplaçant."),
    }  # fmt: skip


def _items(res: httpx.Response) -> list[dict]:
    res.raise_for_status()
    data = res.json()
    return data.get("items", data) if isinstance(data, dict) else data


def main(check_only: bool) -> int:
    missing = 0
    with httpx.Client(base_url=ERP, timeout=10, headers={"x-actor": "user", "x-actor-name": "setup_demo_data"}) as erp:
        today = date.fromisoformat(erp.get("/api/meta").json()["today"][:10])

        # 1. the tag
        tag = build_demo_tag()
        if any(t.get("id") == PROMO_TAG and t.get("scope") == "client" for t in _items(erp.get("/api/tags"))):
            print(f"tag de démo déjà là : {PROMO_TAG}")
        elif check_only:
            print(f"tag de démo absent : {PROMO_TAG}")
            missing += 1
        else:
            erp.post("/api/tags", json=tag).raise_for_status()
            print(f"tag de démo créé : {PROMO_TAG}")

        # 2. the tag on the targets (their other tags kept, never twice)
        for cid in TARGET_CLIENT_IDS:
            res = erp.get(f"/api/clients/{cid}")
            if res.status_code == 404:
                print(f"  {cid} absent de l'ERP : ignoré")
                continue
            tags = res.json().get("tags") or []
            if PROMO_TAG in tags:
                continue
            if check_only:
                print(f"  {cid} sans le tag {PROMO_TAG}")
                missing += 1
            else:
                erp.patch(f"/api/clients/{cid}", json={"tags": [*tags, PROMO_TAG]}).raise_for_status()
                print(f"  {cid} : tag {PROMO_TAG} ajouté")

        # 3. the rule (created, or fixed if an older version targets another group)
        rule = build_demo_rule(today)
        existing = next((r for r in _items(erp.get("/api/price-rules", params={"limit": 500})) if r.get("name") == rule["name"]), None)
        keys = ("clientScope", "productScope", "method", "validFrom", "validTo", "active")
        if existing and all(existing.get(k) == rule[k] for k in keys):
            print(f"promo de démo déjà là : {existing['id']} · {rule['name']}")
        elif check_only:
            print(f"promo de démo {'à corriger' if existing else 'absente'} : {rule['name']}")
            missing += 1
        elif existing:
            erp.patch(f"/api/price-rules/{existing['id']}", json=rule).raise_for_status()
            print(f"promo de démo corrigée : {existing['id']} · {rule['name']} (vise {PROMO_TAG})")
        else:
            res = erp.post("/api/price-rules", json=rule)
            res.raise_for_status()
            print(f"promo de démo créée : {res.json()['id']} · {rule['name']}")

        # 4. what the agent's get_price will see: a target, and a bakery outside the target
        group = [c["id"] for c in _items(erp.get("/api/clients", params={"tag": CLIENT_GROUP, "limit": 500}))]
        outside = next((c for c in group if c not in TARGET_CLIENT_IDS), None)
        for label, cid in (("ciblé", TARGET_CLIENT_IDS[0]), ("hors cible", outside)):
            if cid:
                p = erp.get("/api/prices/resolve", params={"clientId": cid, "productId": PRODUCT_ID, "qty": 30}).json()
                print(f"contrôle ({label}, {cid}, 30 kg) : {p['price']} € — {p['explanation']}")
    return 1 if missing else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create the targeted demo promo in the ERP (idempotent).")
    parser.add_argument("--check", action="store_true", help="only read: is everything there?")
    sys.exit(main(parser.parse_args().check))
