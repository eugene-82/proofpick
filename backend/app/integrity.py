"""Canonical hashes used to bind decision-driving in-memory artifacts."""

import json
from hashlib import sha256
from typing import Any

from pydantic import BaseModel


def canonical_digest(value: Any) -> str:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
