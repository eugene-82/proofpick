"""Orchestration for deterministic source preservation and independence."""

from collections.abc import Iterable

from app.reliability import has_distinct_observation
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

COMMUNITY_DOMAINS = frozenset({"reddit.com", "quora.com"})


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

            fingerprint_content = source.raw_content or source.snippet
            dependency_text = self._normalizer.dependency_text(fingerprint_content)
            copy_text = self._normalizer.copy_text(fingerprint_content)
            content_hash = self._normalizer.content_fingerprint(dependency_text)
            deduplicator = self._registry.deduplicator
            duplicate = deduplicator.find_duplicate(
                normalized_url, content_hash, copy_text
            )
            if duplicate is not None and duplicate.drop:
                representative_key = duplicate.representative_key
                independence_group_id = duplicate.independence_group_id
                current_representative = deduplicator.representative(
                    representative_key
                )
                if (
                    duplicate.can_enrich
                    or normalized_url < current_representative.normalized_url
                ):
                    representative = deduplicator.enrich(
                        representative_key,
                        source,
                        normalized_url=normalized_url,
                        domain=domain,
                        copy_text=copy_text,
                        dependency_text=dependency_text,
                        fingerprint=self._normalizer.content_fingerprint,
                    )
                    self._promote_if_supported(
                        representative,
                        source,
                        copy_text,
                        from_search_result,
                    )
                    representative_key = representative.source_key
                    independence_group_id = representative.independence_group_id
                deduplicator.remember_alias(normalized_url, representative_key)
                self._registry.record_reconciliation()
                dropped.append(
                    DroppedSource(
                        source_key=source_key,
                        original_url=original_url,
                        reason=duplicate.reason,
                        duplicate_of=representative_key,
                        independence_group_id=independence_group_id,
                        independence_state=IndependenceState.DEPENDENT,
                    )
                )
                continue

            state, reasons = self._assess_independence(
                source,
                copy_text,
                from_search_result=from_search_result,
            )
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
                independence_state=state,
                independence_reason_codes=reasons,
            )
            accepted.append(accepted_source)
            deduplicator.remember(accepted_source, copy_text)
            self._registry.record_source(
                source_key, accepted_source.independence_group_id
            )
        return SourceFilterResult(
            accepted_sources=accepted, dropped_sources=dropped
        )

    @staticmethod
    def _assess_independence(
        source: SourceCandidate,
        copy_text: str | None,
        *,
        from_search_result: bool,
    ) -> tuple[IndependenceState, list[IndependenceReasonCode]]:
        if source.independence_state is IndependenceState.CONFIRMED:
            return (
                IndependenceState.CONFIRMED,
                [IndependenceReasonCode.EXPLICITLY_CONFIRMED],
            )
        if source.independence_state is IndependenceState.DEPENDENT:
            return IndependenceState.DEPENDENT, [IndependenceReasonCode.DUPLICATE]
        if (
            from_search_result
            and source.raw_content
            and copy_text
            and has_distinct_observation(copy_text)
        ):
            return (
                IndependenceState.CONFIRMED,
                [IndependenceReasonCode.DISTINCT_SUBSTANTIVE_CONTENT],
            )
        return (
            IndependenceState.UNKNOWN,
            [IndependenceReasonCode.INSUFFICIENT_CONTENT],
        )

    @classmethod
    def _promote_if_supported(
        cls,
        representative: FilteredSource,
        candidate: SourceCandidate,
        copy_text: str | None,
        from_search_result: bool,
    ) -> None:
        state, reasons = cls._assess_independence(
            candidate,
            copy_text,
            from_search_result=from_search_result,
        )
        if state is IndependenceState.CONFIRMED:
            representative.independence_state = state
            representative.independence_reason_codes = reasons

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