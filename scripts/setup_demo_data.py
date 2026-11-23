"""
Team 12 · Demo data that cannot live in git (data/seed/ is git-ignored). OWNER: Daycem (T4).

Real life: while the AOP tourage is out, the wholesaler runs a short promotion on the standard 82 % tourage for its
bakeries, to move stock. Here: one price rule created through the ERP API, so anyone (and the jury, after
`make setup`) can recreate it in one command. FICTIONAL demo data, written in DECISIONS.md §5.

    Rule: group « Boulangeries » × Beurre de tourage 82 % (prd_0026), −8 % on the list price,
          from the ERP business date (GET /api/meta → today) to the end of that month.
    Effect: 9,20 € → 8,46 €/kg for the bakeries without a negotiated price (a negotiated price always wins).

Run after every `make reset` / ERP data reset (a reset erases the rule). Idempotent: does nothing if a rule with the
same name exists. `--check` only reads.

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
PRODUCT_ID = "prd_0026"  # Beurre de tourage 82 % (plaque 2 kg)
CLIENT_TAG = "boulangeries"
DISCOUNT_PCT = 8.0


def build_demo_rule(today: date) -> dict:
    """The PriceRuleInput sent to POST /api/price-rules (pure: tested without the ERP)."""
    end = today.replace(day=calendar.monthrange(today.year, today.month)[1])
    return {
        "name": f"Promo tourage 82 % : −{DISCOUNT_PCT:g} % jusqu'au {end:%d/%m}",
        "active": True,
        "priority": 0,
        "clientScope": {"kind": "tag", "tag": CLIENT_TAG},
        "productScope": {"kind": "product", "productId": PRODUCT_ID},
        "method": {"kind": "discount_pct", "pct": DISCOUNT_PCT},
        "validFrom": today.isoformat(),
        "validTo": end.isoformat(),
        "note": "Données de démo (hackathon) : déstockage du tourage standard pendant la rupture du tourage AOP.",
    }


def main(check_only: bool) -> int:
    with httpx.Client(base_url=ERP, timeout=10, headers={"x-actor": "user", "x-actor-name": "setup_demo_data"}) as erp:
        today = date.fromisoformat(erp.get("/api/meta").json()["today"][:10])
        rule = build_demo_rule(today)
        rules = erp.get("/api/price-rules", params={"limit": 500}).json()
        rules = rules.get("items", rules) if isinstance(rules, dict) else rules
        existing = next((r for r in rules if r.get("name") == rule["name"]), None)
        if existing:
            print(f"promo de démo déjà là : {existing['id']} · {existing['name']}")
        elif check_only:
            print(f"promo de démo absente (à créer : {rule['name']})")
            return 1
        else:
            res = erp.post("/api/price-rules", json=rule)
            res.raise_for_status()
            print(f"promo de démo créée : {res.json()['id']} · {rule['name']}")
        # check what the agent's get_price will see for a bakery without a negotiated price
        price = erp.get("/api/prices/resolve", params={"clientId": "cli_0021", "productId": PRODUCT_ID, "qty": 30}).json()
        print(f"contrôle (Le Pétrin de Colomiers, 30 kg) : {price['price']} € — {price['explanation']}")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create the demo promo in the ERP (idempotent).")
    parser.add_argument("--check", action="store_true", help="only read: is the promo there?")
    sys.exit(main(parser.parse_args().check))
