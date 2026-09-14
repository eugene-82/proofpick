"""Exceptions for query-plan generation."""


class QueryGenerationError(ValueError):
    """Base error raised while building a query plan."""


class UnresolvedProductError(QueryGenerationError):
    """Raised when a product cannot be safely used to form search queries."""


class InvalidQueryStageError(QueryGenerationError):
    """Raised when a requested query-plan stage is not supported."""
