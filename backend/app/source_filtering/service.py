"""Orchestration for deterministic source preservation and independence."""

from collections.abc import Iterable

from app.search.models import SearchResult

from .base import SourceFilter
from .exceptions import InvalidSourceUrlError
from .models import (
    DropReason,
    DroppedSource,
    FilteredSource,
    IndependenceReasonCode,
    IndependenceState,
    SourceCandidate,
    SourceFilterResult,
    SourceType,
)
from .normalizer import SourceNormalizer
from .registry import SourceIdentityRegistry

COMMUNITY_DOMAINS = frozenset(
    {
        "arca.live",
        "dcinside.com",
        "fmkorea.com",
        "quora.com",
        "reddit.com",
        "ruliweb.com",
        "theqoo.net",
    }
)


class DeterministicSourceFilter(SourceFilter):
    def __init__(
        self,
        normalizer: SourceNormalizer | None = None,
        registry: SourceIdentityRegistry | None = None,
    ) -> None:
        self._normalizer = normalizer or SourceNormalizer()
        self._registry = registry or SourceIdentityRegistry()

    @property
    def registry(self) -> SourceIdentityRegistry:
        return self._registry

    def filter(
        self, sources: Iterable[SearchResult | SourceCandidate]
    ) -> SourceFilterResult:
        accepted: list[FilteredSource] = []
        dropped: list[DroppedSource] = []
        for source_input in sources:
            from_search_result = isinstance(source_input, SearchResult)
            source_key = self._registry.next_source_key()
            source = self._as_candidate(source_input)
            original_url = source.url
            try:
                normalized_url = self._normalizer.normalize_url(original_url)
                domain = self._normalizer.domain_from_url(normalized_url)
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

            final_text = source.raw_content or source.snippet
            copy_text = self._normalizer.copy_text(final_text)
            content_hash = self._normalizer.exact_visible_content_fingerprint(
                source.raw_content
            )
            declared_state = self._declared_independence_state(
                source, from_search_result=from_search_result
            )
            deduplicator = self._registry.deduplicator
            duplicate = deduplicator.find_duplicate(
                normalized_url, content_hash, copy_text
            )
            if duplicate is not None:
                representative_key = duplicate.representative_key
                if duplicate.can_enrich:
                    representative = deduplicator.enrich(
                        representative_key,
                        source,
                        normalized_url=normalized_url,
                        domain=domain,
                        copy_text=copy_text,
                        dependency_text=None,
                        fingerprint=self._normalizer.content_fingerprint,
                        declared_state=declared_state,
                    )
                deduplicator.remember_alias(normalized_url, representative_key)
                representative = deduplicator.representative(representative_key)
                self._registry.record_reconciliation()
                dropped.append(
                    DroppedSource(
                        source_key=source_key,
                        original_url=original_url,
                        reason=duplicate.reason,
                        duplicate_of=representative.source_key,
                        independence_group_id=representative.independence_group_id,
                        independence_state=IndependenceState.DEPENDENT,
                    )
                )
                continue

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
                independence_state=IndependenceState.UNKNOWN,
                independence_reason_codes=[
                    IndependenceReasonCode.INSUFFICIENT_CONTENT
                ],
            )
            accepted.append(accepted_source)
            deduplicator.remember(
                accepted_source,
                copy_text,
                declared_state=declared_state,
            )
            self._registry.record_source(
                source_key, accepted_source.independence_group_id
            )
        return SourceFilterResult(
            accepted_sources=accepted, dropped_sources=dropped
        )

    def _declared_independence_state(
        self,
        source: SourceCandidate,
        *,
        from_search_result: bool,
    ) -> IndependenceState:
        if source.independence_state is not IndependenceState.UNKNOWN:
            return source.independence_state
        if (
            from_search_result
            and source.raw_content
            and self._normalizer.has_structural_document_context(
                source.raw_content
            )
        ):
            return IndependenceState.CONFIRMED
        return IndependenceState.UNKNOWN

    @staticmethod
    def _as_candidate(
        source: SearchResult | SourceCandidate,
    ) -> SourceCandidate:
        return (
            SourceCandidate.from_search_result(source)
            if isinstance(source, SearchResult)
            else source
        )

    @staticmethod
    def _is_empty(source: SourceCandidate) -> bool:
        return not any(
            value is not None and value.strip()
            for value in (source.title, source.snippet, source.raw_content)
        )

    @staticmethod
    def _classify_source_type(domain: str) -> SourceType:
        if any(
            domain == known or domain.endswith(f".{known}")
            for known in COMMUNITY_DOMAINS
        ):
            return SourceType.COMMUNITY
        return SourceType.WEB
