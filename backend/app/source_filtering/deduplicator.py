"""Exact and conservative near-duplicate source tracking."""

from dataclasses import dataclass
from difflib import SequenceMatcher

from .models import DropReason, FilteredSource, SourceCandidate


@dataclass(frozen=True)
class DuplicateMatch:
    """The accepted representative for a dependent duplicate."""

    reason: DropReason
    representative_key: str
    independence_group_id: str


class SourceDeduplicator:
    """Track URL, cleaned content, and strong near-copy identity."""

    def __init__(self, near_duplicate_threshold: float = 0.90) -> None:
        if not 0 <= near_duplicate_threshold <= 1:
            raise ValueError("near_duplicate_threshold must be between 0 and 1")
        self._near_duplicate_threshold = near_duplicate_threshold
        self._by_url: dict[str, tuple[str, str]] = {}
        self._by_content_hash: dict[str, tuple[str, str]] = {}
        self._dependency_text_by_key: dict[str, str] = {}
        self._source_by_key: dict[str, FilteredSource] = {}

    def find_duplicate(
        self,
        normalized_url: str,
        content_hash: str | None,
        dependency_text: str | None = None,
    ) -> DuplicateMatch | None:
        url_match = self._by_url.get(normalized_url)
        if url_match is not None:
            return self._match(DropReason.DUPLICATE_URL, url_match)

        if content_hash is not None:
            content_match = self._by_content_hash.get(content_hash)
            if content_match is not None:
                return self._match(DropReason.DUPLICATE_CONTENT, content_match)

        if dependency_text is not None and len(dependency_text.split()) >= 5:
            for source_key, remembered_text in self._dependency_text_by_key.items():
                if len(remembered_text.split()) < 5:
                    continue
                similarity = SequenceMatcher(
                    None, remembered_text, dependency_text, autojunk=False
                ).ratio()
                if similarity >= self._near_duplicate_threshold:
                    source = self._source_by_key[source_key]
                    return DuplicateMatch(
                        reason=DropReason.NEAR_DUPLICATE_CONTENT,
                        representative_key=source.source_key,
                        independence_group_id=source.independence_group_id,
                    )
        return None

    def remember(self, source: FilteredSource, dependency_text: str | None) -> None:
        identity = (source.source_key, source.independence_group_id)
        self._by_url[source.normalized_url] = identity
        if source.content_hash is not None:
            self._by_content_hash[source.content_hash] = identity
        if dependency_text is not None:
            self._dependency_text_by_key[source.source_key] = dependency_text
        self._source_by_key[source.source_key] = source

    def enrich(
        self,
        representative_key: str,
        candidate: SourceCandidate,
        content_hash: str | None,
        dependency_text: str | None,
    ) -> None:
        """Merge richer data from a duplicate URL into its stable representative."""
        source = self._source_by_key[representative_key]
        source.title = self._richer(source.title, candidate.title)
        source.snippet = self._richer(source.snippet, candidate.snippet)
        previous_raw = source.raw_content
        source.raw_content = self._richer(source.raw_content, candidate.raw_content)
        if source.published_at is None:
            source.published_at = candidate.published_at
        if source.raw_content != previous_raw and content_hash is not None:
            source.content_hash = content_hash
        self.remember(source, dependency_text)

    @staticmethod
    def _richer(current: str | None, candidate: str | None) -> str | None:
        if candidate is None or not candidate.strip():
            return current
        if current is None or len(candidate.strip()) > len(current.strip()):
            return candidate
        return current

    @staticmethod
    def _match(reason: DropReason, identity: tuple[str, str]) -> DuplicateMatch:
        return DuplicateMatch(
            reason=reason,
            representative_key=identity[0],
            independence_group_id=identity[1],
        )
