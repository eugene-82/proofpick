"""Provider abstraction required by structured claim extraction."""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any

from app.evidence_processing.models import EvidenceDocument


class ClaimExtractionProvider(ABC):
    """Return one structured payload candidate for an evidence batch."""

    @abstractmethod
    def extract_batch(
        self,
        documents: Sequence[EvidenceDocument],
        *,
        repair: bool = False,
        target_product_id: str = "unspecified-product",
    ) -> Any:
        """Return data to be validated against ClaimExtractionPayload."""
