"""Daycem · T4 · the demo promo created by scripts/setup_demo_data.py (no ERP call here: only the rule it would send)."""

import importlib.util
from datetime import date
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "setup_demo_data.py"
spec = importlib.util.spec_from_file_location("setup_demo_data", SCRIPT)
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def test_demo_rule_targets_the_bakeries_and_the_82_tourage_for_the_rest_of_the_month():
    rule = demo.build_demo_rule(date(2026, 11, 24))
    assert rule["clientScope"] == {"kind": "tag", "tag": "boulangeries"}
    assert rule["productScope"] == {"kind": "product", "productId": "prd_0026"}
    assert rule["method"] == {"kind": "discount_pct", "pct": 8.0}
    assert (rule["validFrom"], rule["validTo"]) == ("2026-11-24", "2026-11-30")
    assert rule["active"] is True
    assert rule["name"] == "82% laminating butter: 8% off until 30/11"
    assert "demo" in rule["note"].lower()  # data modified on purpose, said in the ERP itself


def test_the_end_date_follows_the_erp_business_date():
    assert demo.build_demo_rule(date(2026, 12, 10))["validTo"] == "2026-12-31"
    assert demo.build_demo_rule(date(2027, 2, 3))["validTo"] == "2027-02-28"
