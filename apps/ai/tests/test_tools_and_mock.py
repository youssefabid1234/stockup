"""The @tool decorator's JSON schemas and the mock LLM's French formatting."""

from datetime import date

from pydantic import Field

from app.clients.mock_llm import command_client, command_date, detect_intent, extract_query, fr_day, fr_num, parse_line
from app.tools import TOOLS
from app.tools.registry import ToolContext, json_schema, tool


def test_schema_of_a_new_tool():
    @tool(name="demo_tool")
    async def demo(ctx: ToolContext, client_id: str = Field(description="ex. cli_1"), limit: float | None = None) -> dict:
        """
        First line.
        Line two.
        """
        return {"client_id": client_id, "limit": limit}

    try:
        assert demo.info.to_wire() == {
            "name": "demo_tool",
            "description": "First line. Line two.",
            "parameters": {
                "type": "object",
                "properties": {"clientId": {"type": "string", "description": "ex. cli_1"}, "limit": {"type": "number"}},
                "required": ["clientId"],
            },
        }
    finally:
        TOOLS.pop("demo_tool")


async def test_tool_validates_arguments():
    @tool(name="demo_add")
    async def demo_add(ctx: ToolContext, qty: float) -> float:
        """Add one."""
        return qty + 1

    try:
        assert await demo_add.run({"qty": 2}, ctx=None) == 3
        try:
            await demo_add.run({"qty": "many"}, ctx=None)
        except ValueError as e:
            assert str(e).startswith("Invalid arguments: qty:")
        else:
            raise AssertionError("expected a validation error")
    finally:
        TOOLS.pop("demo_add")


def test_nested_model_is_inlined():
    schema = json_schema(TOOLS["create_draft_order"].args_model)
    assert "$defs" not in schema
    assert schema["properties"]["lines"]["items"]["required"] == ["productId", "qty"]


def test_english_formatting():
    assert fr_num(45.52) == "45.52"
    assert fr_num(4) == "4"
    assert fr_num(1234.5) == "1,234.5"
    assert fr_num(2.005) == "2"  # 2.005 is 2.00499… in binary, like JavaScript
    assert fr_day("2026-11-25") == "Wednesday 25 November"


def test_mock_understanding():
    assert extract_query("Hello, do you have any sea bass?") == "sea bass"
    assert detect_intent("I'd like 4 kg of sea bass") == "line"
    assert parse_line("I'd like 4 kg of sea bass for tomorrow.").qty == 4
    assert parse_line("two dozen oysters").product == "oysters"
    assert command_client("creates a pre-order for Lemoine, 4 kilos of bar for Thursday") == "lemoine"
    assert command_date("for Thursday", "… (2026-11-24) …") == "2026-11-26"
    assert command_date("for Tuesday", "… (2026-11-24) …") == "2026-12-01"  # never today
    assert date.fromisoformat(command_date("tomorrow", "(2026-11-24)")) == date(2026, 11, 25)
