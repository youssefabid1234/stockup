"""
Team 12 · Demo data that cannot live in git (data/seed/ is git-ignored). OWNER: Daycem.

Real life: the wholesaler runs a one-week promotion on standard tourage to move stock while the AOP is out.
Here: create it through the ERP API, so anyone (and the jury, after `make setup`) can recreate it in one command.
Run after every `make reset` / ERP data reset:

    apps/ai/.venv/Scripts/python scripts/setup_demo_data.py        (mac/linux: apps/ai/.venv/bin/python)

TODO(Daycem):
  1. read the price-rule schema: http://localhost:4000/docs → POST /api/price-rules (PriceRule input)
  2. create e.g. "Promo tourage 82 % : −8 % jusqu'au 30/11" on prd_0026, valid 24/11 → 30/11/2026, idempotent
     (skip if a rule with the same name exists: GET /api/price-rules)
  3. check: GET /api/prices/resolve?clientId=cli_0021&productId=prd_0026 shows the discounted price
  4. write it in DECISIONS.md (data modified for the demo, on purpose)
"""

import sys

import httpx

ERP = "http://localhost:4000"
DEMO_RULE_NAME = "Promo tourage 82 % : −8 % jusqu'au 30/11"


def main() -> int:
    rules = httpx.get(f"{ERP}/api/price-rules", timeout=10).json()
    rules = rules.get("items", rules) if isinstance(rules, dict) else rules
    if any(r.get("name") == DEMO_RULE_NAME for r in rules):
        print("demo promo already there")
        return 0
    print("TODO(Daycem): create the demo promo (see the docstring)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
