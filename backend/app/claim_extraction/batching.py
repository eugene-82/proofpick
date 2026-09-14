"""Stable bounded batching for evidence documents."""

from collections.abc import Iterable

from app.evidence_processing.models import EvidenceDocument

from .policy import ClaimExtractionPolicy


class ClaimBatcher:
    """Preserve input order while enforcing document and character limits."""

    def __init__(self, policy: ClaimExtractionPolicy) -> None:
        self._policy = policy

    def batches(self, documents: Iterable[EvidenceDocument]) -> list[list[EvidenceDocument]]:
        batches: list[list[EvidenceDocument]] = []
        current: list[EvidenceDocument] = []
        current_chars = 0

        for document in documents:
            document_chars = len(document.text)
            if document_chars > self._policy.max_total_chars_per_batch:
                raise ValueError(
                    f"{document.source_key} exceeds max_total_chars_per_batch; "
                    "bound evidence before claim extraction"
                )

            exceeds_count = len(current) == self._policy.max_documents_per_batch
            exceeds_chars = current_chars + document_chars > self._policy.max_total_chars_per_batch
            if current and (exceeds_count or exceeds_chars):
                batches.append(current)
                current = []
                current_chars = 0

            current.append(document)
            current_chars += document_chars

        if current:
            batches.append(current)
        return batches
