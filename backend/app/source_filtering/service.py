"""Orchestration for deterministic source filtering."""

from collections.abc import Iterable

from app.search.models import SearchResult

from .base import SourceFilter
from .exceptions import InvalidSourceUrlError
from .models import (
    DropReason,
    DroppedSource,
    FilteredSource,
    IndependenceState,
    SourceCandidate,
    SourceFilterResult,
    SourceType,
)
from .normalizer import SourceNormalizer
from .registry import SourceIdentityRegistry


COMMUNITY_DOMAINS = frozenset(
    {
        "reddit.com",
        "quora.com",
    }
)


class DeterministicSourceFilter(SourceFilter):
    """Remove invalid and dependent sources across incremental snapshot runs."""

    def __init__(
        self,
        normalizer: SourceNormalizer | None = None,
        registry: SourceIdentityRegistry | None = None,
    ) -> None:
        self._normalizer = normalizer or SourceNormalizer()
        self._registry = registry or SourceIdentityRegistry()

    def filter(
        self,
        sources: Iterable[SearchResult | SourceCandidate],
    ) -> SourceFilterResult:
        accepted: list[FilteredSource] = []
        dropped: list[DroppedSource] = []

        for source_input in sources:
            source_key = self._registry.next_source_key()
            source = self._as_candidate(source_input)
            original_url = source.url

            try:
                normalized_url = self._normalizer.normalize_url(original_url)
            except InvalidSourceUrlError:
                dropped.append(
                    DroppedSource(
                        source_key=source_key,
                        original_url=original_url,
                        reason=DropReason.INVALID_URL,
                    )
                )
                continue

            if self._is_empty(source):
                dropped.append(
                    DroppedSource(
                        source_key=source_key,
                        original_url=original_url,
                        reason=DropReason.EMPTY_CONTENT,
                    )
                )
                continue

            fingerprint_content = (
                source.raw_content
                if source.raw_content and source.raw_content.strip()
                else source.snippet
            )
            dependency_text = self._normalizer.dependency_text(fingerprint_content)
            content_hash = self._normalizer.content_fingerprint(dependency_text)
            deduplicator = self._registry.deduplicator
            duplicate = deduplicator.find_duplicate(
                normalized_url, content_hash, dependency_text
            )
            if duplicate is not None:
                if duplicate.reason is DropReason.DUPLICATE_URL:
                    deduplicator.enrich(
                        duplicate.representative_key,
                        source,
                        content_hash,
                        dependency_text,
                    )
                dropped.append(
                    DroppedSource(
                        source_key=source_key,
                        original_url=original_url,
                        reason=duplicate.reason,
                        duplicate_of=duplicate.representative_key,
                        independence_group_id=duplicate.independence_group_id,
                        independence_state=IndependenceState.DEPENDENT,
                    )
                )
                continue

            domain = self._normalizer.domain_from_url(normalized_url)
            accepted_source = FilteredSource(
                source_key=source_key,
                original_url=original_url or "",
                normalized_url=normalized_url,
                domain=domain,
                title=source.title,
                snippet=source.snippet,
                raw_content=source.raw_content,
                published_at=source.published_at,
                source_type=source.source_type or self._classify_source_type(domain),
                content_hash=content_hash,
                independence_group_id=self._registry.next_group_id(),
                independence_state=source.independence_state,
            )
            accepted.append(accepted_source)
            deduplicator.remember(accepted_source, dependency_text)

        return SourceFilterResult(accepted_sources=accepted, dropped_sources=dropped)

    @staticmethod
    def _as_candidate(source: SearchResult | SourceCandidate) -> SourceCandidate:
        if isinstance(source, SearchResult):
            return SourceCandidate.from_search_result(source)
        return source

    @staticmethod
    def _is_empty(source: SourceCandidate) -> bool:
        return not any(
            value is not None and value.strip()
            for value in (source.title, source.snippet, source.raw_content)
        )

    @staticmethod
    def _classify_source_type(domain: str) -> SourceType:
        if any(domain == known or domain.endswith(f".{known}") for known in COMMUNITY_DOMAINS):
            return SourceType.COMMUNITY
        return SourceType.WEB
