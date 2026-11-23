"""Base class of every wire model: Python attributes in snake_case, JSON in camelCase."""

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


def _type_is_required(schema: dict) -> None:
    """Events and messages have `type: Literal[...] = "..."`: a default for Python, but always on the wire.
    Mark it required in the JSON schema so generated TypeScript types can narrow on it."""
    if "type" in schema.get("properties", {}) and "type" not in schema.get("required", []):
        schema["required"] = ["type", *schema.get("required", [])]


class WireModel(BaseModel):
    """`tool_call_id` in Python is `toolCallId` on the wire (requests are accepted in both spellings)."""

    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, serialize_by_alias=True, json_schema_extra=_type_is_required
    )

    def to_wire(self) -> dict:
        """JSON-ready dict, camelCase, unset optional fields left out (like `undefined` in JavaScript)."""
        return self.model_dump(mode="json", by_alias=True, exclude_none=True)

    def to_json(self) -> str:
        return self.model_dump_json(by_alias=True, exclude_none=True)
