"""Provider-independent search interface."""

from abc import ABC, abstractmethod

from .models import SearchResult


class SearchProvider(ABC):
    """Return normalized results for exactly one supplied query."""

    @abstractmethod
    def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        include_raw_content: bool = False,
    ) -> list[SearchResult]:
        """Run one query without applying query-budget business rules."""
