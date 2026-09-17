"""Structured extraction, retry, grounding, and failure reporting."""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.evidence_processing.models import EvidenceDocument

from .base import ClaimExtractionProvider
from .batching import ClaimBatcher
from .exceptions import (
    ClaimGroundingError,
    ClaimOutputValidationError,
    ClaimProviderError,
)
from .grounding import ClaimGroundingValidator
from .models import (
    ClaimExtractionFailure,
    ClaimExtractionPayload,
    ClaimExtractionResult,
    ExtractionFailureCode,
    GroundingAssessment,
)
from .policy import ClaimExtractionPolicy


@dataclass(frozen=True)
class _RejectedBatch(Exception):
    code: ExtractionFailureCode
    message: str
    assessments: tuple[GroundingAssessment, ...] = ()


class StructuredClaimExtractor:
    """Accept only structurally valid and VERIFIED claims."""

    def __init__(
        self,
        provider: ClaimExtractionProvider,
        policy: ClaimExtractionPolicy = ClaimExtractionPolicy(),
        grounding_validator: ClaimGroundingValidator | None = None,
    ) -> None:
        self._provider = provider
        self._batcher = ClaimBatcher(policy)
        self._grounding = grounding_validator or ClaimGroundingValidator()

    def extract(self, documents: Iterable[EvidenceDocument]) -> ClaimExtractionResult:
        document_list = list(documents)
        source_ids = [document.source_key for document in document_list]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("evidence source IDs must be unique")

        claims = []
        assessments: list[GroundingAssessment] = []
        failures: list[ClaimExtractionFailure] = []
        for batch_index, batch in enumerate(self._batcher.batches(document_list), start=1):
            try:
                payload, batch_assessments = self._extract_validated_batch(batch)
            except ClaimProviderError as error:
                failures.append(
                    self._failure(
                        batch_index,
                        batch,
                        ExtractionFailureCode.PROVIDER_ERROR,
                        str(error),
                    )
                )
            except _RejectedBatch as error:
                assessments.extend(error.assessments)
                failures.append(self._failure(batch_index, batch, error.code, error.message))
            else:
                claims.extend(payload.claims)
                assessments.extend(batch_assessments)
        return ClaimExtractionResult(
            claims=claims,
            grounding_assessments=assessments,
            failures=failures,
        )

    def _extract_validated_batch(
        self, batch: Sequence[EvidenceDocument]
    ) -> tuple[ClaimExtractionPayload, list[GroundingAssessment]]:
        last_error: Exception | None = None
        last_assessments: tuple[GroundingAssessment, ...] = ()
        failure_code = ExtractionFailureCode.MALFORMED_OUTPUT

        for attempt in range(2):
            try:
                output: Any = self._provider.extract_batch(
                    batch,
                    repair=attempt == 1,
                    target_product_id=self._grounding.target_product_id,
                )
                payload = ClaimExtractionPayload.model_validate(output)
                return self._grounding.validate_with_assessments(
                    payload, batch, repair=attempt == 1
                )
            except (ValidationError, ClaimOutputValidationError) as error:
                last_error = error
                failure_code = ExtractionFailureCode.MALFORMED_OUTPUT
                last_assessments = ()
            except ClaimGroundingError as error:
                last_error = error
                failure_code = ExtractionFailureCode.GROUNDING_ERROR
                last_assessments = error.assessments

        raise _RejectedBatch(
            code=failure_code,
            message=str(last_error) or "claim output validation failed",
            assessments=last_assessments,
        )

    @staticmethod
    def _failure(
        batch_index: int,
        batch: Sequence[EvidenceDocument],
        code: ExtractionFailureCode,
        message: str,
    ) -> ClaimExtractionFailure:
        return ClaimExtractionFailure(
            batch_index=batch_index,
            source_ids=[document.source_key for document in batch],
            code=code,
            message=message,
        )
