"""OpenAI strict JSON-schema normalization for structured claim output."""

from copy import deepcopy
from typing import Any

from pydantic import BaseModel


def strict_model_json_schema(model: type[BaseModel]) -> dict[str, Any]:
    """Return a strict schema while preserving nullable field semantics.

    OpenAI strict structured output requires every object property to be listed
    in ``required``. Optional application values therefore remain nullable, but
    are not optional omissions in the provider response.
    """

    schema = deepcopy(model.model_json_schema())
    return _normalize_node(schema)


def _normalize_node(node: Any) -> Any:
    if isinstance(node, list):
        return [_normalize_node(item) for item in node]
    if not isinstance(node, dict):
        return node

    normalized = {
        key: _normalize_node(value)
        for key, value in node.items()
        if key != "default"
    }
    properties = normalized.get("properties")
    if isinstance(properties, dict):
        normalized["additionalProperties"] = False
        normalized["required"] = list(properties)
    return normalized
