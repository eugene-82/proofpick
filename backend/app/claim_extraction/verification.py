"""Abstain-capable semantic verification boundary.

The embedded adapter reuses a structured verdict from the extraction provider,
so the default path needs no second paid call. A TASK 013 verifier may replace it.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.evidence_processing.models import EvidenceDocument

from .models import (
    ClaimVerificationVerdict,
    ExtractedClaim,
    GroundingState,
)


class ClaimVerificationProvider(ABC):
    @abstractmethod
    def verify_batch(
        self,
        claims: Sequence[ExtractedClaim],
        documents: Sequence[EvidenceDocument],
        *,
        target_product_id: str,
        repair: bool = False,
    ) -> Sequence[ClaimVerificationVerdict]:
        """Return one structured, candidate-bound verdict per claim."""


class EmbeddedClaimVerificationProvider(ClaimVerificationProvider):
    """Use extraction-provider semantics without making another API call."""

    def verify_batch(
        self,
        claims: Sequence[ExtractedClaim],
        documents: Sequence[EvidenceDocument],
        *,
        target_product_id: str,
        repair: bool = False,
    ) -> Sequence[ClaimVerificationVerdict]:
        return [
            ClaimVerificationVerdict(
                claim=claim,
                relation=claim.semantic_relation,
                verification_status=(
                    claim.semantic_relation.verification_status
                    if claim.semantic_relation is not None
                    else GroundingState.UNCERTAIN
                ),
                detail=(
                    "structured semantic verdict supplied by extraction provider"
                    if claim.semantic_relation is not None
                    else "no structured semantic verdict was supplied"
                ),
            )
            for claim in claims
        ]
