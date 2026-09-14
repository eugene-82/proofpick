"""Source filtering interface."""

from abc import ABC, abstractmethod
from collections.abc import Iterable

from app.search.models import SearchResult

from .models import SourceCandidate, SourceFilterResult


class SourceFilter(ABC):
    """Filter and deduplicate provider results before claim extraction."""

    @abstractmethod
    def filter(
        self,
        sources: Iterable[SearchResult | SourceCandidate],
    ) -> SourceFilterResult:
        """Return accepted sources and traceable drops in input order."""
