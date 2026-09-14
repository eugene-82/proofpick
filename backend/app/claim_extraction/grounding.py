"""Deterministic source and evidence grounding checks."""

import re
from collections.abc import Sequence

from app.evidence_processing.models import EvidenceDocument

from .exceptions import ClaimGroundingError
from .models import ClaimExtractionPayload, ExtractedClaim


MONTH_PATTERN = re.compile(r"(?<!\d)(\d+)\s*(?:개월|months?)\b", re.IGNORECASE)
YEAR_PATTERN = re.compile(r"(?<!\d)(\d+)\s*(?:년|years?)\b", re.IGNORECASE)


class ClaimGroundingValidator:
    """Reject source mismatches, unsupported fragments, and guessed durations."""

    def validate(
        self,
        payload: ClaimExtractionPayload,
        documents: Sequence[EvidenceDocument],
    ) -> ClaimExtractionPayload:
        document_by_id = {document.source_key: document for document in documents}
        indexed_claims = list(enumerate(payload.claims))

        for _, claim in indexed_claims:
            document = document_by_id.get(claim.source_id)
            if document is None:
                raise ClaimGroundingError(
                    f"claim references source_id {claim.source_id} outside its batch"
                )
            self._validate_fragment(claim, document)
            self._validate_usage_period(claim, document)

        source_order = {document.source_key: index for index, document in enumerate(documents)}
        ordered_claims = [
            claim
            for _, claim in sorted(
                indexed_claims,
                key=lambda item: (source_order[item[1].source_id], item[0]),
            )
        ]
        return ClaimExtractionPayload(claims=ordered_claims)

    @staticmethod
    def _validate_fragment(claim: ExtractedClaim, document: EvidenceDocument) -> None:
        fragment = ClaimGroundingValidator._normalize_for_match(claim.evidence_fragment)
        source_text = ClaimGroundingValidator._normalize_for_match(document.text)
        if fragment not in source_text:
            raise ClaimGroundingError(
                f"evidence_fragment for {claim.source_id} is not present in source text"
            )

    @staticmethod
    def _validate_usage_period(claim: ExtractedClaim, document: EvidenceDocument) -> None:
        if claim.usage_period_months is None:
            return
        explicit_months = {int(value) for value in MONTH_PATTERN.findall(document.text)}
        explicit_months.update(12 * int(value) for value in YEAR_PATTERN.findall(document.text))
        if claim.usage_period_months not in explicit_months:
            raise ClaimGroundingError(
                f"usage_period_months for {claim.source_id} is not explicit in source text"
            )

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        return " ".join(text.casefold().split())
