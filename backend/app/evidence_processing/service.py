"""Deterministic orchestration for reusable bounded evidence."""

from collections.abc import Iterable

from app.source_filtering.models import FilteredSource

from .base import EvidenceProcessor
from .cleaner import EvidenceCleaner
from .compressor import EvidenceCompressor
from .models import EvidenceDocument, EvidenceSource
from .policy import DEFAULT_EVIDENCE_BUDGET_POLICY, EvidenceBudgetPolicy


class DeterministicEvidenceProcessor(EvidenceProcessor):
    """Clean each accepted source once and preserve all source provenance."""

    def __init__(
        self,
        policy: EvidenceBudgetPolicy = DEFAULT_EVIDENCE_BUDGET_POLICY,
        cleaner: EvidenceCleaner | None = None,
    ) -> None:
        self._cleaner = cleaner or EvidenceCleaner()
        self._compressor = EvidenceCompressor(policy)

    def process(self, source: FilteredSource) -> EvidenceDocument | None:
        selected_text, evidence_source = self._select_text(source)
        if selected_text is None:
            return None

        original_length = len(selected_text)
        cleaned_text = self._cleaner.clean(selected_text)
        if not cleaned_text:
            return None

        compressed = self._compressor.compress(cleaned_text)
        compressed_length = len(compressed.text)
        return EvidenceDocument(
            source_key=source.source_key,
            original_url=source.original_url,
            normalized_url=source.normalized_url,
            domain=source.domain,
            title=source.title,
            text=compressed.text,
            evidence_source=evidence_source,
            original_length=original_length,
            compressed_length=compressed_length,
            compression_ratio=compressed_length / original_length if original_length else 0,
            truncated=compressed.truncated,
            content_hash=source.content_hash,
            source_type=source.source_type,
            independence_group_id=source.independence_group_id,
        )

    def process_all(self, sources: Iterable[FilteredSource]) -> list[EvidenceDocument]:
        return [document for source in sources if (document := self.process(source)) is not None]

    @staticmethod
    def _select_text(source: FilteredSource) -> tuple[str | None, EvidenceSource | None]:
        if source.raw_content is not None and source.raw_content.strip():
            return source.raw_content, EvidenceSource.RAW_CONTENT
        if source.snippet is not None and source.snippet.strip():
            return source.snippet, EvidenceSource.SNIPPET
        return None, None
