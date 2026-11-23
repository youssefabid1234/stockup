"""Base classes of every schema.

Python attributes are snake_case; the JSON (and the OpenAPI contract) is camelCase via aliases.
Optional fields are simply omitted from responses when they have no value (never `null`).
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, model_serializer


def to_camel(name: str) -> str:
    """snake_case → camelCase: "vat_rate" → "vatRate", "revenue_30d" → "revenue30d"."""
    first, *rest = name.split("_")
    return first + "".join(part[:1].upper() + part[1:] for part in rest)


class Schema(BaseModel):
    """A response / document shape. Serialized with camelCase keys, without None values."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    @model_serializer(mode="wrap")
    def _omit_none(self, handler: Any) -> Any:
        data = handler(self)
        return {k: v for k, v in data.items() if v is not None} if isinstance(data, dict) else data


class Input(Schema):
    """A request body: strict types (no "5" → 5 coercion), unknown keys ignored."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, strict=True)

    def data(self) -> dict[str, Any]:
        """The fields that were sent (plus defaults), camelCase, as a plain dict for the services."""
        return self.model_dump(by_alias=True)
