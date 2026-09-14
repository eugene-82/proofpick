"""Small standard-library vector helpers."""

import math
from collections.abc import Sequence

from .exceptions import EmbeddingValidationError


def normalize_vector(vector: Sequence[float]) -> tuple[float, ...]:
    if not vector:
        raise EmbeddingValidationError("embedding vector must not be empty")

    values: list[float] = []
    for value in vector:
        if isinstance(value, bool):
            raise EmbeddingValidationError("embedding values must be finite numbers")
        try:
            numeric = float(value)
        except (TypeError, ValueError) as error:
            raise EmbeddingValidationError("embedding values must be finite numbers") from error
        if not math.isfinite(numeric):
            raise EmbeddingValidationError("embedding values must be finite numbers")
        values.append(numeric)

    magnitude = math.sqrt(sum(value * value for value in values))
    if magnitude == 0:
        raise EmbeddingValidationError("embedding vector must not be zero")
    return tuple(value / magnitude for value in values)


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right):
        raise EmbeddingValidationError("embedding dimensions must match")
    return sum(left_value * right_value for left_value, right_value in zip(left, right))
