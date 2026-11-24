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
        Première ligne.
        Deuxième ligne.
        """
        return {"client_id": client_id, "limit": limit}

    try:
        assert demo.info.to_wire() == {
            "name": "demo_tool",
            "description": "Première ligne. Deuxième ligne.",
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
            await demo_add.run({"qty": "beaucoup"}, ctx=None)
        except ValueError as e:
            assert str(e).startswith("Arguments invalides : qty:")
        else:
            raise AssertionError("expected a validation error")
    finally:
        TOOLS.pop("demo_add")


def test_nested_model_is_inlined():
    schema = json_schema(TOOLS["create_draft_order"].args_model)
    assert "$defs" not in schema
    assert schema["properties"]["lines"]["items"]["required"] == ["productId", "qty"]


def test_french_formatting():
    assert fr_num(45.52) == "45,52"
    assert fr_num(4) == "4"
    assert fr_num(1234.5) == "1 234,5"
    assert fr_num(2.005) == "2"  # 2.005 is 2.00499… in binary, like JavaScript
    assert fr_day("2026-11-25") == "le mercredi 25 novembre"


def test_mock_understanding():
    assert extract_query("Bonjour, il vous reste du bar ?") == "bar"
    assert detect_intent("je voudrais 4 kg de bar de ligne") == "line"
    assert parse_line("je voudrais 4 kg de bar de ligne pour demain").qty == 4
    assert parse_line("deux douzaines d'huîtres").product == "huîtres"
    assert command_client("crée une pré-commande pour Lemoine, 4 kilos de bar pour jeudi") == "lemoine"
    assert command_date("pour jeudi", "… (2026-11-24) …") == "2026-11-26"
    assert command_date("pour mardi", "… (2026-11-24) …") == "2026-12-01"  # never today
    assert date.fromisoformat(command_date("demain", "(2026-11-24)")) == date(2026, 11, 25)
