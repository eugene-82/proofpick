"""Exact source duplicate tracking."""

from dataclasses import dataclass

from .models import DropReason, FilteredSource


@dataclass(frozen=True)
class DuplicateMatch:
    """The accepted representative for an exact duplicate."""

    reason: DropReason
    representative_key: str
    independence_group_id: str


class SourceDeduplicator:
    """Track exact URL and content identity without semantic guesses."""

    def __init__(self) -> None:
        self._by_url: dict[str, tuple[str, str]] = {}
        self._by_content_hash: dict[str, tuple[str, str]] = {}

    def find_duplicate(
        self, normalized_url: str, content_hash: str | None
    ) -> DuplicateMatch | None:
        url_match = self._by_url.get(normalized_url)
        if url_match is not None:
            return DuplicateMatch(
                reason=DropReason.DUPLICATE_URL,
                representative_key=url_match[0],
                independence_group_id=url_match[1],
            )

        if content_hash is not None:
            content_match = self._by_content_hash.get(content_hash)
            if content_match is not None:
                return DuplicateMatch(
                    reason=DropReason.DUPLICATE_CONTENT,
                    representative_key=content_match[0],
                    independence_group_id=content_match[1],
                )
        return None

    def remember(self, source: FilteredSource) -> None:
        identity = (source.source_key, source.independence_group_id)
        self._by_url[source.normalized_url] = identity
        if source.content_hash is not None:
            self._by_content_hash[source.content_hash] = identity
