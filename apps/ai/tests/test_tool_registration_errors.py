"""@tool fails fast, with a clear French message, on the common beginner mistakes."""

import pytest

from app.tools import TOOLS
from app.tools.registry import ToolContext, tool


def test_existing_tools_registered():
    assert TOOLS


def test_not_async():
    with pytest.raises(TypeError, match="async def"):

        @tool(name="bad_sync")
        def bad_sync(ctx: ToolContext) -> dict:
            """Doc."""
            return {}


def test_first_param_not_ctx():
    with pytest.raises(TypeError, match="ctx: ToolContext"):

        @tool(name="bad_ctx")
        async def bad_ctx(context: ToolContext) -> dict:
            """Doc."""
            return {}


def test_no_params_at_all():
    with pytest.raises(TypeError, match="ctx: ToolContext"):

        @tool(name="bad_noparams")
        async def bad_noparams() -> dict:
            """Doc."""
            return {}


def test_untyped_param():
    with pytest.raises(TypeError, match="`qty` doit avoir un type"):

        @tool(name="bad_untyped")
        async def bad_untyped(ctx: ToolContext, qty) -> dict:
            """Doc."""
            return {}


def test_missing_docstring():
    with pytest.raises(TypeError, match="docstring"):

        @tool(name="bad_nodoc")
        async def bad_nodoc(ctx: ToolContext) -> dict:
            return {}


def test_duplicate_name():
    existing = next(iter(TOOLS))
    with pytest.raises(TypeError, match="un outil porte déjà ce nom"):

        @tool(name=existing)
        async def dup(ctx: ToolContext) -> dict:
            """Doc."""
            return {}
