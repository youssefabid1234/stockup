"""Daycem · T4 · the demo promo: scripts/setup_demo_data.py (through the ERP API) and apps/backend/app/core/team_demo.py
(Youssef: added to the data pack at every reset) must build exactly the same tag, the same targets and the same rule."""

import importlib.util
import sys
import types
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("setup_demo_data", ROOT / "scripts" / "setup_demo_data.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


def _team_demo(seed_dir_name="seed"):
    """Load the backend's team_demo.py alone: its two imports (.db, .config) are replaced by tiny stand-ins."""
    pkg = types.ModuleType("fake_backend_core")
    pkg.__path__ = []
    db = types.ModuleType("fake_backend_core.db")
    db.Doc = dict
    config = types.ModuleType("fake_backend_core.config")
    config.SEED_DIR = Path("/data") / seed_dir_name
    sys.modules.update({"fake_backend_core": pkg, "fake_backend_core.db": db, "fake_backend_core.config": config})
    s = importlib.util.spec_from_file_location("fake_backend_core.team_demo", ROOT / "apps/backend/app/core/team_demo.py")
    mod = importlib.util.module_from_spec(s)
    s.loader.exec_module(mod)
    return mod


TODAY = date(2026, 11, 24)


def test_demo_rule_targets_the_promo_tag_and_the_82_tourage_for_the_rest_of_the_month():
    rule = demo.build_demo_rule(TODAY)
    assert rule["clientScope"] == {"kind": "tag", "tag": "promo-tourage"}  # no longer every « boulangeries »
    assert rule["productScope"] == {"kind": "product", "productId": "prd_0026"}
    assert rule["method"] == {"kind": "discount_pct", "pct": 8.0}
    assert (rule["validFrom"], rule["validTo"]) == ("2026-11-24", "2026-11-30")
    assert rule["active"] is True and rule.get("minQty") is None
    assert rule["name"] == "Promo tourage 82 % : −8 % jusqu'au 30/11"
    assert "démo" in rule["note"].lower()  # data modified on purpose, said in the ERP itself


def test_the_end_date_follows_the_erp_business_date():
    assert demo.build_demo_rule(date(2026, 12, 10))["validTo"] == "2026-12-31"
    assert demo.build_demo_rule(date(2027, 2, 3))["validTo"] == "2027-02-28"


def test_the_frozen_target_is_the_six_aop_buyers_who_accept_a_substitute():
    assert demo.TARGET_CLIENT_IDS == ["cli_0020", "cli_0033", "cli_0060", "cli_0070", "cli_0085", "cli_0102"]
    assert "cli_0001" not in demo.TARGET_CLIENT_IDS and "cli_0021" not in demo.TARGET_CLIENT_IDS


def test_team_demo_and_the_script_build_exactly_the_same_tag_targets_and_rule():
    td = _team_demo()
    assert td.TARGET_CLIENT_IDS == demo.TARGET_CLIENT_IDS
    assert td.PROMO_TAG == demo.PROMO_TAG and td.PRODUCT_ID == demo.PRODUCT_ID and td.DISCOUNT_PCT == demo.DISCOUNT_PCT
    assert td.demo_tag() == demo.build_demo_tag()
    rule = td.demo_price_rule(TODAY)
    assert {k: v for k, v in rule.items() if k not in ("id", "createdAt")} == demo.build_demo_rule(TODAY)


def _pack():
    return {
        "meta": {"today": "2026-11-24"},
        "products": [{"id": "prd_0026"}],
        "tags": [{"id": "boulangeries", "scope": "client", "label": "Boulangeries"}],
        "clients": [{"id": "cli_0070", "tags": ["boulangeries"]}, {"id": "cli_0021", "tags": ["boulangeries", "grands-comptes"]}],
        "priceRules": [],
    }


def test_the_pack_gets_the_tag_on_the_targets_only_and_one_rule_even_twice():
    td = _team_demo()
    pack = _pack()
    td.add_team_demo_data(pack)
    td.add_team_demo_data(pack)  # a second read of the pack changes nothing
    clients = {c["id"]: c["tags"] for c in pack["clients"]}
    assert clients["cli_0070"] == ["boulangeries", "promo-tourage"]  # the other tags are kept
    assert clients["cli_0021"] == ["boulangeries", "grands-comptes"]  # outside the target
    assert [t["id"] for t in pack["tags"]].count("promo-tourage") == 1
    assert len(pack["priceRules"]) == 1 and pack["priceRules"][0]["clientScope"] == {"kind": "tag", "tag": "promo-tourage"}


def test_another_company_pack_is_left_alone():
    td = _team_demo()
    pack = _pack()
    pack["clients"] = [{"id": "cli_9999", "tags": []}]
    assert td.add_team_demo_data(pack) == [] and pack["priceRules"] == []


def test_english_pack_gets_english_labels_and_the_same_targeting():
    td = _team_demo("seed_en")
    assert td.demo_price_rule(TODAY)["name"].startswith("Promo 82% laminating butter")
    assert td.demo_price_rule(TODAY)["clientScope"] == {"kind": "tag", "tag": "promo-tourage"}
    assert td.demo_tag()["label"] != demo.build_demo_tag()["label"]  # English label


def test_the_script_logic_names_no_client_and_no_product():
    """Ids live in the constants at the top (demo data); main() and the builders only use them."""
    import inspect

    for fn in (demo.main, demo.build_demo_rule, demo.build_demo_tag):
        code = inspect.getsource(fn)
        assert "cli_" not in code and "prd_" not in code, fn.__name__
