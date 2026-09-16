"""Orchestration for deterministic source filtering."""

from collections.abc import Iterable

from app.search.models import SearchResult

from .base import SourceFilter
from .exceptions import InvalidSourceUrlError
from .models import (
    DropReason, DroppedSource, FilteredSource, IndependenceReasonCode,
    IndependenceState, SourceCandidate, SourceFilterResult, SourceType,
)
from .normalizer import SourceNormalizer
from .registry import SourceIdentityRegistry

COMMUNITY_DOMAINS = frozenset({"reddit.com", "quora.com"})


class DeterministicSourceFilter(SourceFilter):
    def __init__(self, normalizer: SourceNormalizer | None = None,
                 registry: SourceIdentityRegistry | None = None) -> None:
        self._normalizer = normalizer or SourceNormalizer()
        self._registry = registry or SourceIdentityRegistry()

    @property
    def registry(self) -> SourceIdentityRegistry:
        return self._registry

    def filter(self, sources: Iterable[SearchResult | SourceCandidate]) -> SourceFilterResult:
        accepted: list[FilteredSource] = []
        dropped: list[DroppedSource] = []
        for source_input in sources:
            source_key = self._registry.next_source_key()
            source = self._as_candidate(source_input)
            original_url = source.url
            try:
                normalized_url = self._normalizer.normalize_url(original_url)
            except InvalidSourceUrlError:
                dropped.append(DroppedSource(source_key=source_key, original_url=original_url,
                                             reason=DropReason.INVALID_URL))
                continue
            if self._is_empty(source):
                dropped.append(DroppedSource(source_key=source_key, original_url=original_url,
                                             reason=DropReason.EMPTY_CONTENT))
                continue
            fingerprint_content = (
                source.raw_content
                if source.raw_content and source.raw_content.strip()
                else source.snippet
            )
            dependency_text = self._normalizer.dependency_text(fingerprint_content)
            content_hash = self._normalizer.content_fingerprint(dependency_text)
            deduplicator = self._registry.deduplicator
            duplicate = deduplicator.find_duplicate(normalized_url, content_hash, dependency_text)
            if duplicate is not None and duplicate.drop:
                representative_key = duplicate.representative_key
                independence_group_id = duplicate.independence_group_id
                if duplicate.reason is DropReason.DUPLICATE_URL and duplicate.can_enrich:
                    representative = deduplicator.enrich(
                        representative_key, source,
                        self._normalizer.dependency_text,
                        self._normalizer.content_fingerprint,
                    )
                    representative_key = representative.source_key
                    independence_group_id = representative.independence_group_id
                deduplicator.remember_alias(normalized_url, representative_key)
                self._registry.record_reconciliation()
                dropped.append(DroppedSource(
                    source_key=source_key, original_url=original_url, reason=duplicate.reason,
                    duplicate_of=representative_key,
                    independence_group_id=independence_group_id,
                    independence_state=IndependenceState.DEPENDENT,
                ))
                continue
            domain = self._normalizer.domain_from_url(normalized_url)
            state, reasons = self._assess_independence(source, dependency_text, duplicate)
            accepted_source = FilteredSource(
                source_key=source_key, original_url=original_url or "",
                normalized_url=normalized_url, domain=domain, title=source.title,
                snippet=source.snippet, raw_content=source.raw_content,
                published_at=source.published_at,
                source_type=source.source_type or self._classify_source_type(domain),
                content_hash=content_hash, independence_group_id=self._registry.next_group_id(),
                independence_state=state, independence_reason_codes=reasons,
            )
            accepted.append(accepted_source)
            deduplicator.remember(accepted_source, dependency_text)
            self._registry.record_source(source_key, accepted_source.independence_group_id)
        return SourceFilterResult(accepted_sources=accepted, dropped_sources=dropped)

    @staticmethod
    def _assess_independence(source, dependency_text, duplicate):
        if source.independence_state is IndependenceState.CONFIRMED:
            return IndependenceState.CONFIRMED, [IndependenceReasonCode.EXPLICITLY_CONFIRMED]
        if source.independence_state is IndependenceState.DEPENDENT:
            return IndependenceState.DEPENDENT, [IndependenceReasonCode.DUPLICATE]
        if duplicate is not None and not duplicate.drop:
            return IndependenceState.UNKNOWN, [IndependenceReasonCode.POSSIBLE_NEAR_DUPLICATE]
        return IndependenceState.UNKNOWN, [IndependenceReasonCode.INSUFFICIENT_CONTENT]

    @staticmethod
    def _as_candidate(source):
        return SourceCandidate.from_search_result(source) if isinstance(source, SearchResult) else source

    @staticmethod
    def _is_empty(source):
        return not any(value is not None and value.strip()
                       for value in (source.title, source.snippet, source.raw_content))

    @staticmethod
    def _classify_source_type(domain):
        if any(domain == known or domain.endswith(f".{known}") for known in COMMUNITY_DOMAINS):
            return SourceType.COMMUNITY
        return SourceType.WEB
