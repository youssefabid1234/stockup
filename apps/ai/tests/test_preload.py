"""Youssef · T2: the caller's sheet is found in the conversation, loaded once, cleaned of notes the ERP contradicts."""

import json

import pytest

from app.agent import call_context as cc_mod
from app.agent.call_context import contradicts_delivery_days, drop_contradictions, identify_client, render_for_prompt
from app.schemas import ChatMessage, ToolCall

CLIENT = {
    "id": "cli_0021", "name": "Le Pétrin de Colomiers", "status": "active", "deliveryDays": ["mon", "wed"],
    "preferences": "Delivered Mon. Sea. Accept equivalent substitutions if warned.",
    "usual": [{"productId": "prd_0025", "productName": "Touring AOP", "unit": "kg", "avgQty": 30}],
    "notes": [{"at": "2025-09-01T00:00:00Z", "author": "Karim", "text": "Closed on Wednesdays: never delivered that day."},
              {"at": "2026-01-01T00:00:00Z", "author": "Karim", "text": "Closed on Sundays."}],
}  # fmt: skip
CONTEXT = {"entries": [{"kind": "fact", "title": "Latest notes CRM",
                        "body": "- 01/09/2025, Karim : Closed on Wednesday: never delivered that day.\n- Pay in LCR"}]}  # fmt: skip


class FakeErp:
    def __init__(self):
        self.calls = []

    async def get(self, path, params=None):
        self.calls.append(path)
        if path.startswith("/api/clients/"):
            return CLIENT
        if path == "/api/context/for":
            return CONTEXT
        if path.startswith("/api/products/"):
            return {"id": path.rsplit("/", 1)[1], "available": 0}
        raise AssertionError(path)


@pytest.fixture(autouse=True)
def fresh_cache():
    cc_mod.clear_cache()
    yield
    cc_mod.clear_cache()


def tool_turn(name: str, result) -> list[ChatMessage]:
    return [
        ChatMessage(role="user", content="Hello"),
        ChatMessage(role="assistant", content="", tool_calls=[ToolCall(id="c1", name=name, arguments={})]),
        ChatMessage(role="tool", tool_call_id="c1", name=name, content=json.dumps(result)),
    ]


def test_identify_client_from_get_client_or_a_single_search_hit():
    assert identify_client([ChatMessage(role="user", content="Hello")]) is None
    assert identify_client(tool_turn("get_client", {"id": "cli_0021", "name": "x"})) == "cli_0021"
    one = [{"type": "client", "id": "cli_0001", "label": "Maison Sarrailh"}, {"type": "product", "id": "prd_0001"}]
    assert identify_client(tool_turn("search", one)) == "cli_0001"
    two = [{"type": "client", "id": "cli_0001"}, {"type": "client", "id": "cli_0002"}]
    assert identify_client(tool_turn("search", two)) is None  # ambiguous: the agent must ask


def test_closed_day_notes_are_dropped_only_when_the_erp_delivers_that_day():
    assert contradicts_delivery_days("Closed on Wednesday: never delivered", ["mon", "wed"])
    assert not contradicts_delivery_days("Closed on Sundays", ["mon", "wed"])  # not a delivery day: keep
    assert not contradicts_delivery_days("Delivered on a closing day", ["mon", "wed"])
    assert drop_contradictions("- Closed on Wednesdays\n- Pay in LCR", ["wed"]) == "- Pay in LCR"


async def test_sheet_is_loaded_clean_with_usual_stock():
    sheet = await cc_mod.load_call_context(FakeErp(), "cli_0021")
    assert all("Wednesday" not in n for n in sheet.notes) and any("Sunday" in n for n in sheet.notes)
    assert "Closed on Wednesday" not in sheet.context_entries[0]["body"] and "LCR" in sheet.context_entries[0]["body"]
    assert sheet.usual[0].available == 0
    text = render_for_prompt(sheet)
    assert "Do not search for this caller again" in text and "Delivery days (ERP, even if a note says otherwise)" in text and "Monday, Wednesday" in text
    assert "Closed on Wednesday" not in text and "stock 0" in text


async def test_context_for_loads_once_then_uses_the_cache():
    erp = FakeErp()
    messages = tool_turn("get_client", {"id": "cli_0021"})
    first = await cc_mod.context_for(messages, erp)
    n = len(erp.calls)
    second = await cc_mod.context_for(messages, erp)
    assert first is second and len(erp.calls) == n  # no second ERP round-trip


async def test_prefetch_then_context_for_waits_for_the_background_load():
    erp = FakeErp()
    cc_mod.prefetch(erp, "cli_0021")
    cc_mod.prefetch(erp, "cli_0021")  # twice: one load only
    sheet = await cc_mod.context_for(tool_turn("get_client", {"id": "cli_0021"}), erp)
    assert sheet.name == "Le Pétrin de Colomiers" and erp.calls.count("/api/clients/cli_0021") == 1


async def test_no_client_no_sheet():
    assert await cc_mod.context_for([ChatMessage(role="user", content="Hello")], FakeErp()) is None
