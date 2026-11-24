"""
The tool registry and the @tool decorator.

A tool = an async function the model can call. The decorator turns its signature into the JSON schema
sent to the model, and its docstring into the description:

    @tool
    async def get_product_stock(ctx: ToolContext, product_id: str = Field(description="ex. prd_0042")) -> dict:
        \"\"\"Stock d'un produit : disponible, arrivages, prochaine DLC, prix catalogue.\"\"\"
        return await ctx.erp.get(f"/api/products/{product_id}")

  - first parameter: the ToolContext (ERP client tagged with the actor);
  - the other parameters are the tool's arguments. snake_case in Python, camelCase for the model
    (`product_id` → `productId`). Use pydantic `Field(...)` to describe them, `Literal[...]` for enums,
    `X | None = None` for optional ones, a pydantic model for nested objects;
  - the docstring is the description the model reads (lines are joined with spaces): say WHEN to use it;
  - return small JSON-able data (every byte is re-read by the model). Raise to report an error:
    the agent loop turns it into `{"error": "..."}` and the model explains or retries.
"""

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, create_model
from pydantic.alias_generators import to_camel

from app.schemas import ToolInfo

from .erp import Actor, ErpClient


@dataclass
class ToolContext:
    erp: ErpClient  # HTTP client for the ERP API, already tagged with x-actor
    actor: Actor  # "ai_chat" (web chat) or "voice_agent" (phone / voice commands)


class ToolArgs(BaseModel):
    """Base of the generated argument models (and of nested argument objects): camelCase for the model."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


@dataclass
class Tool:
    name: str
    description: str
    args_model: type[ToolArgs]  # validates what the model sends
    fn: Callable[..., Awaitable[Any]]

    @property
    def info(self) -> ToolInfo:
        return ToolInfo(name=self.name, description=self.description, parameters=json_schema(self.args_model))

    async def run(self, arguments: dict[str, Any], ctx: ToolContext) -> Any:
        try:
            args = self.args_model.model_validate(arguments)
        except ValidationError as e:
            problems = "; ".join(f"{'.'.join(map(str, err['loc']))}: {err['msg']}" for err in e.errors())
            raise ValueError(f"Arguments invalides : {problems}") from None
        return await self.fn(ctx, **{name: getattr(args, name) for name in type(args).model_fields})


TOOLS: dict[str, Tool] = {}


def tool(fn: Callable[..., Awaitable[Any]] | None = None, *, name: str | None = None):
    """Register an async function as a tool. Use as `@tool` or `@tool(name="other_name")`."""

    def register(fn: Callable[..., Awaitable[Any]]) -> Tool:
        tool_name = name or fn.__name__
        # Fail fast, at import time, on the common mistakes (clear message instead of a silent misbehaviour).
        if not inspect.iscoroutinefunction(fn):
            raise TypeError(f"@tool {tool_name} : la fonction doit être `async def` (must be async)")
        all_params = list(inspect.signature(fn).parameters.values())
        if not all_params or all_params[0].name != "ctx":
            raise TypeError(f"@tool {tool_name} : le premier paramètre doit être `ctx: ToolContext`")
        params = all_params[1:]  # skip ctx
        for p in params:
            if p.annotation is inspect.Parameter.empty:
                raise TypeError(f"@tool {tool_name} : le paramètre `{p.name}` doit avoir un type, ex. `{p.name}: str`")
        description = " ".join(line.strip() for line in inspect.cleandoc(fn.__doc__ or "").splitlines() if line.strip())
        if not description:
            raise TypeError(f"@tool {tool_name} : ajoutez une docstring (c'est la description que lit le modèle)")
        if tool_name in TOOLS:
            raise TypeError(f"@tool {tool_name} : un outil porte déjà ce nom")
        fields = {
            p.name: (p.annotation, ... if p.default is inspect.Parameter.empty else p.default) for p in params
        }
        args_model = create_model(f"{fn.__name__}_args", __base__=ToolArgs, **fields)
        t = Tool(name=tool_name, description=description, args_model=args_model, fn=fn)
        TOOLS[t.name] = t
        return t

    return register(fn) if fn else register


# ── JSON schema, kept as small as possible for the model ──


def json_schema(model: type[BaseModel]) -> dict:
    """Pydantic's schema without titles / defaults / $refs / `| null`, i.e. what you would write by hand."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def clean(node: Any) -> Any:
        if isinstance(node, list):
            return [clean(x) for x in node]
        if not isinstance(node, dict):
            return node
        if "$ref" in node:  # nested model: inline it
            node = {**defs[node["$ref"].split("/")[-1]], **{k: v for k, v in node.items() if k != "$ref"}}
        if "anyOf" in node:  # `X | None` → X
            options = [o for o in node["anyOf"] if o != {"type": "null"}]
            if len(options) == 1:
                node = {**clean(options[0]), **{k: v for k, v in node.items() if k != "anyOf"}}
        return {
            k: (clean(v) if k != "properties" else {name: clean(p) for name, p in v.items()})
            for k, v in node.items()
            if k not in ("title", "default")
        }

    return clean(schema)
