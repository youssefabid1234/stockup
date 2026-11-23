"""Team 12 skeleton: with every TEAM_* switch off, the kit behaves exactly as before; the hook points exist."""

import json
from pathlib import Path

import pytest

from app import team_flags
from app.agent import call_context as cc_mod
from app.agent import orchestrator, prompts, rules_order, rules_sales
from app.agent.call_context import CallContext, UsualItem, render_for_prompt
from app.services import fillers

FLAGS = ["TEAM_FILLERS", "TEAM_ORCHESTRATOR", "TEAM_PRELOAD", "TEAM_PRODUCT_INSIGHT", "TEAM_ORDER_RULES", "TEAM_SALES_RULES"]
REPO = Path(__file__).resolve().parents[3]


@pytest.fixture(autouse=True)
def switches_off(monkeypatch):
    for f in FLAGS:
        monkeypatch.delenv(f, raising=False)


@pytest.fixture
def offline_prompt(monkeypatch):
    async def meta():
        return {"company": "Le Fournil Occitan", "today": "2026-11-24"}

    monkeypatch.setattr(prompts, "get_meta", meta)
    monkeypatch.setattr(prompts, "read_context_files", lambda: "CONTEXTE")


def sheet(**kw) -> CallContext:
    base = dict(
        client_id="cli_0001",
        name="Maison Sarrailh",
        delivery_days=["tue", "thu", "sat"],
        preferences="Jamais de substitution sur le beurre",
        usual=[UsualItem("prd_0001", "Farine tradition", "sac", avg_qty=10, available=40)],
    )
    return CallContext(**{**base, **kw})


def test_all_switches_off_by_default():
    assert not any(team_flags.all_flags().values())


async def test_prompt_unchanged_when_switches_off(offline_prompt):
    text = await prompts.build_system_prompt("voice")
    assert "CONTEXTE" in text and "Client au téléphone" not in text


async def test_rules_sections_appear_only_when_switched_on(offline_prompt, monkeypatch):
    monkeypatch.setattr(rules_order, "ORDER_RULES", "REGLE-COMMANDE")
    monkeypatch.setattr(rules_sales, "SALES_RULES", "REGLE-VENTE")
    assert "REGLE-COMMANDE" not in await prompts.build_system_prompt("voice")
    monkeypatch.setenv("TEAM_ORDER_RULES", "1")
    monkeypatch.setenv("TEAM_SALES_RULES", "1")
    text = await prompts.build_system_prompt("voice")
    assert "REGLE-COMMANDE" in text and "REGLE-VENTE" in text
    assert text.index("REGLE-COMMANDE") < text.index("CONTEXTE")  # static rules before the big cached context
    assert "REGLE-COMMANDE" not in await prompts.build_system_prompt("command")  # one-shot command mode untouched


async def test_call_context_goes_last_in_the_prompt(offline_prompt):
    text = await prompts.build_system_prompt("voice", call_context=sheet())
    assert text.index("CONTEXTE") < text.index("Client au téléphone : Maison Sarrailh")


def test_render_call_context():
    assert render_for_prompt(None) == ""
    text = render_for_prompt(sheet())
    assert "Jamais de substitution sur le beurre" in text and "mardi, jeudi, samedi" in text and "stock 40" in text
    assert "COMPTE BLOQUÉ" in render_for_prompt(sheet(status="blocked"))


async def test_orchestrator_delegates_to_the_kit_loop(monkeypatch):
    seen = {}

    async def fake_run_agent(messages, **kw):
        seen.update(kw)
        yield "event"

    monkeypatch.setattr(orchestrator, "run_agent", fake_run_agent)
    events = [ev async for ev in orchestrator.run_voice_turn([], llm=None, tools=[], call_context=sheet())]
    assert events == ["event"] and seen["call_context"].name == "Maison Sarrailh"


async def test_fillers_do_nothing_when_off():
    class NoSpeaker:
        def __getattr__(self, name):  # any call on the speaker would fail the test
            raise AssertionError(f"speaker.{name} called while TEAM_FILLERS is off")

    await fillers.on_turn_start(NoSpeaker(), "bonjour")
    await fillers.on_tool_call(NoSpeaker(), "search")


def test_product_insight_not_registered_when_off():
    from app.tools import TOOLS

    assert "product_insight" not in TOOLS


async def test_load_call_context_reads_client_and_context_in_parallel():
    class FakeErp:
        async def get(self, path, params=None):
            if path.startswith("/api/clients/"):
                return {"id": "cli_0001", "name": "Maison Sarrailh", "status": "active", "deliveryDays": ["tue"],
                        "preferences": "AOP", "usual": [{"productId": "prd_0001", "productName": "Tradi", "unit": "sac", "avgQty": 10}],
                        "notes": [{"at": "2026-06-02T00:00:00Z", "author": "Julien", "text": "Allocation AOP"}]}  # fmt: skip
            return {"entries": [{"kind": "risk", "title": "Ce qui les agace", "body": "Une substitution sur le tourage"}]}

    cc = await cc_mod.load_call_context(FakeErp(), "cli_0001")
    assert cc.name == "Maison Sarrailh" and cc.usual[0].avg_qty == 10 and cc.context_entries[0]["kind"] == "risk"
    assert cc.loaded_ms is not None


def test_scenarios_are_valid():
    files = sorted((REPO / "scenarios").glob("*.json"))
    assert files, "scenarios/*.json missing"
    for f in files:
        s = json.loads(f.read_text(encoding="utf-8"))
        assert {"id", "owner", "title", "turns"} <= s.keys(), f.name
        assert all("say" in t for t in s["turns"]), f.name
