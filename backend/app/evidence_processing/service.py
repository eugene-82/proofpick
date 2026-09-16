"""Deterministic orchestration for reusable bounded evidence."""

import re
from collections.abc import Iterable

from app.source_filtering.models import FilteredSource

from .base import EvidenceProcessor
from .cleaner import EvidenceCleaner
from .compressor import EvidenceCompressor
from .models import (
    EvidenceDocument, EvidenceQuality, EvidenceSource, ObservationState,
)
from .policy import DEFAULT_EVIDENCE_BUDGET_POLICY, EvidenceBudgetPolicy


FIRST_IMPRESSION_PATTERN = re.compile(
    r"\b(?:first\s+day|day\s+one|today|just\s+(?:got|bought|opened)|initial\s+impression)\b|"
    r"(?:첫날|첫\s*인상|오늘)", re.I
)
OBSERVATION_CLAUSE_SPLIT = re.compile(r"\s*(?:[.!?;]|\band\b|\bbut\b)\s*", re.I)
NON_OBSERVATION_DURATION_PATTERN = re.compile(
    r"\b(?:warranty|subscription|return\s+period|trial|coverage)\b", re.I
)
ESTABLISHED_USAGE_PATTERN = re.compile(
    r"\b(?:i|we)\s+(?:have\s+)?(?:used|owned|tested|had)\b[^.!?;]{0,60}"
    r"\bfor\s+(?:\d+|a|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
    r"(?:weeks?|months?|years?)\b|"
    r"\bafter\s+(?:\d+|a|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s+"
    r"(?:weeks?|months?|years?)\s+(?:of\s+)?(?:daily\s+)?(?:use|usage|ownership|testing)\b|"
    r"(?:\d+\s*(?:주|개월|년)(?:간|째)?\s*(?:사용|이용|써|썼))",
    re.I,
)


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
            observation_state=self._observation_state(cleaned_text),
            content_coverage_ratio=ratio,
            grounding_text=compressed.grounding_text,
            grounding_eligible=compressed.grounding_eligible,
        )

    def process_all(self, sources: Iterable[FilteredSource]) -> list[EvidenceDocument]:
        return [document for source in sources if (document := self.process(source)) is not None]

    @staticmethod
    def _observation_state(text: str) -> ObservationState:
        clauses = [
            clause.strip()
            for clause in OBSERVATION_CLAUSE_SPLIT.split(text)
            if clause.strip()
        ]
        established = any(
            ESTABLISHED_USAGE_PATTERN.search(clause)
            and not NON_OBSERVATION_DURATION_PATTERN.search(clause)
            for clause in clauses
        )
        if established:
            return ObservationState.ESTABLISHED
        if any(FIRST_IMPRESSION_PATTERN.search(clause) for clause in clauses):
            return ObservationState.FIRST_IMPRESSION
        return ObservationState.UNKNOWN

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
