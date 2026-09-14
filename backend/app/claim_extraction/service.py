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
)
from .policy import ClaimExtractionPolicy


@dataclass(frozen=True)
class _RejectedBatch(Exception):
    code: ExtractionFailureCode
    message: str


class StructuredClaimExtractor:
    """Validate and ground batched provider output before accepting claims."""

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
        failures: list[ClaimExtractionFailure] = []
        for batch_index, batch in enumerate(self._batcher.batches(document_list), start=1):
            try:
                payload = self._extract_validated_batch(batch)
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
                failures.append(self._failure(batch_index, batch, error.code, error.message))
            else:
                claims.extend(payload.claims)
        return ClaimExtractionResult(claims=claims, failures=failures)

    def _extract_validated_batch(
        self, batch: Sequence[EvidenceDocument]
    ) -> ClaimExtractionPayload:
        last_error: Exception | None = None
        failure_code = ExtractionFailureCode.MALFORMED_OUTPUT

        for attempt in range(2):
            try:
                output: Any = self._provider.extract_batch(batch, repair=attempt == 1)
                payload = ClaimExtractionPayload.model_validate(output)
                return self._grounding.validate(payload, batch)
            except (ValidationError, ClaimOutputValidationError) as error:
                last_error = error
                failure_code = ExtractionFailureCode.MALFORMED_OUTPUT
            except ClaimGroundingError as error:
                last_error = error
                failure_code = ExtractionFailureCode.GROUNDING_ERROR

        raise _RejectedBatch(
            code=failure_code,
            message=str(last_error) or "claim output validation failed",
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
