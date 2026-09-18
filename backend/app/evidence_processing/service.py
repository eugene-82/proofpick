"""Deterministic orchestration for reusable bounded evidence."""

from collections.abc import Iterable

from app.source_filtering.models import FilteredSource

from .base import EvidenceProcessor
from .cleaner import EvidenceCleaner
from .compressor import EvidenceCompressor
from .models import (
    EvidenceDocument, EvidenceQuality, EvidenceSource, ObservationState,
)
from .policy import DEFAULT_EVIDENCE_BUDGET_POLICY, EvidenceBudgetPolicy


class DeterministicEvidenceProcessor(EvidenceProcessor):
    def __init__(self, policy: EvidenceBudgetPolicy = DEFAULT_EVIDENCE_BUDGET_POLICY,
                 cleaner: EvidenceCleaner | None = None) -> None:
        self._cleaner = cleaner or EvidenceCleaner()
        self._compressor = EvidenceCompressor(policy)

    def process(self, source: FilteredSource) -> EvidenceDocument | None:
        selected_text, evidence_source = self._select_text(source)
        if selected_text is None:
            return None
        cleaned_text = self._cleaner.clean(selected_text)
        if not cleaned_text and evidence_source is EvidenceSource.RAW_CONTENT:
            selected_text, evidence_source = self._select_snippet(source)
            if selected_text is not None:
                cleaned_text = self._cleaner.clean(selected_text)
        if not cleaned_text or selected_text is None or evidence_source is None:
            return None

        original_length = len(selected_text)
        compressed = self._compressor.compress(cleaned_text)
        compressed_length = len(compressed.text)
        ratio = compressed_length / original_length if original_length else 0
        quality = (
            EvidenceQuality.SNIPPET_ONLY
            if evidence_source is EvidenceSource.SNIPPET
            else EvidenceQuality.PARTIAL_CONTENT
            if compressed.truncated
            else EvidenceQuality.FULL_CONTENT
        )
        return EvidenceDocument(
            source_key=source.source_key, original_url=source.original_url,
            normalized_url=source.normalized_url, domain=source.domain, title=source.title,
            text=compressed.text, evidence_source=evidence_source,
            original_length=original_length, compressed_length=compressed_length,
            compression_ratio=ratio, truncated=compressed.truncated,
            content_hash=source.content_hash, source_type=source.source_type,
            independence_group_id=source.independence_group_id,
            independence_state=source.independence_state, evidence_quality=quality,
            observation_state=ObservationState.UNKNOWN,
            content_coverage_ratio=ratio,
            grounding_text=compressed.grounding_text,
            grounding_eligible=compressed.grounding_eligible,
            segments=compressed.segments,
            evidence_coverage_limited=compressed.evidence_coverage_limited,
            unsafe_partial_risk=compressed.unsafe_partial_risk,
        )

    def process_all(self, sources: Iterable[FilteredSource]) -> list[EvidenceDocument]:
        return [document for source in sources if (document := self.process(source)) is not None]

    @staticmethod
    def _select_text(source: FilteredSource):
        if source.raw_content is not None and source.raw_content.strip():
            return source.raw_content, EvidenceSource.RAW_CONTENT
        return DeterministicEvidenceProcessor._select_snippet(source)

    @staticmethod
    def _select_snippet(source: FilteredSource):
        if source.snippet is not None and source.snippet.strip():
            return source.snippet, EvidenceSource.SNIPPET
        return None, None
