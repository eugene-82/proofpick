"""Inspectable confidence inputs and outputs."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.source_filtering.models import FilteredSource, IndependenceState


class ConfidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ConfidenceSourceMetadata(ConfidenceModel):
    """Source provenance plus optional measured commercial signal."""

    source_id: str = Field(pattern=r"^S\d{3,}$")
    domain: str = Field(min_length=1)
    independence_group_id: str = Field(pattern=r"^IG\d{3,}$")
    independence_state: IndependenceState = IndependenceState.CONFIRMED
    commercial_signal: float | None = Field(default=None, ge=0, le=1)

    @classmethod
    def from_filtered_source(cls, source: FilteredSource) -> "ConfidenceSourceMetadata":
        return cls(
            source_id=source.source_key,
            domain=source.domain,
            independence_group_id=source.independence_group_id,
            independence_state=source.independence_state,
            commercial_signal=None,
        )


class ConfidenceComponentBreakdown(ConfidenceModel):
    """Normalized component scores retained for UI and debugging."""

    evidence_volume_score: float = Field(ge=0, le=1)
    independence_score: float = Field(ge=0, le=1)
    diversity_score: float = Field(ge=0, le=1)
    agreement_score: float = Field(ge=0, le=1)
    long_term_score: float = Field(ge=0, le=1)
    commercial_risk_score: float = Field(ge=0, le=1)


class ConfidenceEvidenceMetrics(ConfidenceModel):
    """Raw evidence counts behind the normalized component scores."""

    cluster_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    independent_source_count: int = Field(ge=0)
    domain_count: int = Field(ge=0)
    long_term_source_count: int = Field(ge=0)
    long_term_independent_source_count: int = Field(ge=0)
    commercial_signal_group_count: int = Field(ge=0)


class ConfidenceResult(ConfidenceModel):
    """Evidence confidence; it is deliberately not a product-quality score."""

    overall_score: float = Field(ge=0, le=1)
    confidence_level: ConfidenceLevel
    components: ConfidenceComponentBreakdown
    commercial_risk_penalty: float = Field(ge=0, le=1)
    metrics: ConfidenceEvidenceMetrics
