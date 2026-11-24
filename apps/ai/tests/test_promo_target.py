"""Daycem · T4 · who gets the demo promo: scripts/promo_target.py (generic, no name or id in the code).

Rule (DECISIONS §5): clients of a group, active, with at least N orders of the product now out of stock over the last
M months, and whose card does not refuse substitutes. The frozen list in setup_demo_data.py must match it on the data.
"""

import importlib.util
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pt = _load("promo_target")
TODAY = date(2026, 11, 24)


def _client(cid, tags=("bakery",), status="active", refuses=False):
    return {"id": cid, "tags": list(tags), "status": status, "refuses": refuses}


def _order(cid, day, pid="p_out", status="invoiced"):
    return {"clientId": cid, "status": status, "deliveryDate": day, "lines": [{"productId": pid, "qty": 10}]}


def _select(clients, orders, **kw):
    args = {"client_tag": "bakery", "product_id": "p_out", "min_orders": 2, "months": 12, "today": TODAY,
            "refuses": lambda c: c["refuses"]}  # fmt: skip
    return pt.select_targets(clients, orders, **{**args, **kw})


def test_two_orders_in_the_last_twelve_months_are_needed():
    clients = [_client("a"), _client("b")]
    orders = [_order("a", "2026-03-01"), _order("a", "2026-10-01"), _order("b", "2026-10-01")]
    assert _select(clients, orders) == ["a"]


def test_old_cancelled_draft_and_other_product_orders_do_not_count():
    clients = [_client("a")]
    orders = [_order("a", "2025-06-01"), _order("a", "2026-10-01", status="cancelled"), _order("a", "2026-10-02", status="draft"),
              _order("a", "2026-10-03", pid="p_other"), _order("a", "2026-10-04")]  # fmt: skip
    assert _select(clients, orders) == []


def test_blocked_refusing_and_other_group_clients_are_out():
    clients = [_client("blocked", status="blocked"), _client("refuses", refuses=True), _client("other", tags=("cafe",)), _client("ok")]
    orders = [_order(c["id"], d) for c in clients for d in ("2026-05-01", "2026-09-01")]
    assert _select(clients, orders) == ["ok"]


def test_one_order_with_two_lines_counts_once():
    clients = [_client("a")]
    o = _order("a", "2026-10-01")
    o["lines"].append({"productId": "p_out", "qty": 5})
    assert _select(clients, [o]) == []


def test_result_is_sorted_and_without_duplicates():
    clients = [_client("z"), _client("a")]
    orders = [_order(c, d) for c in ("z", "a") for d in ("2026-05-01", "2026-09-01")]
    assert _select(clients, orders) == ["a", "z"]


def test_the_code_names_no_client_and_no_product():
    code = (ROOT / "scripts" / "promo_target.py").read_text(encoding="utf-8").lower()
    for word in ["cli_", "prd_", "boulangeries", "tourage", "sarrailh", "colomiers", "guilhem"]:
        assert word not in code, f"promo_target.py mentions {word!r}"


def test_the_frozen_list_matches_the_data():
    """The list in setup_demo_data.py is frozen on purpose (DECISIONS §5); this test says when the data moved away."""
    from app.config import settings

    seed = Path(settings.data_dir) / "seed"
    if not (seed / "orders.json").exists():
        pytest.skip("needs DATA_DIR/seed")
    demo = _load("setup_demo_data")
    computed = pt.targets_from_pack(seed, client_tag=demo.CLIENT_GROUP, product_id=demo.OUT_OF_STOCK_PRODUCT_ID,
                                    min_orders=2, months=12)  # fmt: skip
    assert computed == demo.TARGET_CLIENT_IDS
