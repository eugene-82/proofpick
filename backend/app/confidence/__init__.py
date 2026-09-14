"""Deterministic evidence-confidence scoring for clustered claims."""

from .exceptions import ConfidenceInputError
from .models import (
    ConfidenceComponentBreakdown,
    ConfidenceEvidenceMetrics,
    ConfidenceLevel,
    ConfidenceResult,
    ConfidenceSourceMetadata,
)
from .policy import ConfidencePolicy
from .service import EvidenceConfidenceEngine

__all__ = [
    "ConfidenceComponentBreakdown",
    "ConfidenceEvidenceMetrics",
    "ConfidenceInputError",
    "ConfidenceLevel",
    "ConfidencePolicy",
    "ConfidenceResult",
    "ConfidenceSourceMetadata",
    "EvidenceConfidenceEngine",
]
