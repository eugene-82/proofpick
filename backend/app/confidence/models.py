"""Inspectable confidence inputs and outputs."""

from enum import Enum
from pydantic import BaseModel, ConfigDict, Field
from app.evidence_processing.models import EvidenceDocument, EvidenceQuality, ObservationState
from app.integrity import canonical_digest
from app.source_filtering.models import FilteredSource, IndependenceState

class ConfidenceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class ConfidenceQualityIssue(str, Enum):
    SNIPPET_ONLY_COVERAGE = "snippet_only_coverage"
    NO_VERIFIED_CLAIM_COVERAGE = "no_verified_claim_coverage"
    UNKNOWN_SOURCE_QUALITY = "unknown_source_quality"
    INSUFFICIENT_DURABILITY_OBSERVATION = "insufficient_durability_observation"
    UNSAFE_PARTIAL_EVIDENCE = "unsafe_partial_evidence"

class ConfidenceSourceMetadata(ConfidenceModel):
    source_id: str = Field(pattern=r"^S\d{3,}$")
    domain: str = Field(min_length=1)
    independence_group_id: str = Field(pattern=r"^IG\d{3,}$")
    independence_state: IndependenceState = IndependenceState.CONFIRMED
    commercial_signal: float | None = Field(default=None, ge=0, le=1)
    evidence_quality: EvidenceQuality = EvidenceQuality.UNKNOWN
    observation_state: ObservationState = ObservationState.UNKNOWN
    verified_claim_count: int = Field(default=0, ge=0)
    extracted_claim_count: int = Field(default=0, ge=0)
    evidence_coverage_limited: bool = False

    @classmethod
    def from_filtered_source(cls, source: FilteredSource) -> "ConfidenceSourceMetadata":
        quality = (EvidenceQuality.FULL_CONTENT if source.raw_content and source.raw_content.strip()
                   else EvidenceQuality.SNIPPET_ONLY if source.snippet
                   else EvidenceQuality.UNKNOWN)
        return cls(source_id=source.source_key, domain=source.domain,
                   independence_group_id=source.independence_group_id,
                   independence_state=source.independence_state,
                   evidence_quality=quality)

    @classmethod
    def from_evidence_document(cls, document: EvidenceDocument, *,
                               verified_claim_count: int,
                               extracted_claim_count: int) -> "ConfidenceSourceMetadata":
        return cls(source_id=document.source_key, domain=document.domain,
                   independence_group_id=document.independence_group_id,
                   independence_state=document.independence_state,
                   evidence_quality=document.evidence_quality,
                   observation_state=document.observation_state,
                   evidence_coverage_limited=document.evidence_coverage_limited,
                   verified_claim_count=verified_claim_count,
                   extracted_claim_count=extracted_claim_count)

class ConfidenceComponentBreakdown(ConfidenceModel):
    evidence_volume_score: float = Field(ge=0, le=1)
    independence_score: float = Field(ge=0, le=1)
    diversity_score: float = Field(ge=0, le=1)
    agreement_score: float = Field(ge=0, le=1)
    long_term_score: float = Field(ge=0, le=1)
    commercial_risk_score: float = Field(ge=0, le=1)

class ConfidenceEvidenceMetrics(ConfidenceModel):
    cluster_count: int = Field(ge=0)
    source_count: int = Field(ge=0)
    independent_source_count: int = Field(ge=0)
    domain_count: int = Field(ge=0)
    long_term_source_count: int = Field(ge=0)
    long_term_independent_source_count: int = Field(ge=0)
    commercial_signal_group_count: int = Field(ge=0)

class ConfidenceResult(ConfidenceModel):
    overall_score: float = Field(ge=0, le=1)
    confidence_level: ConfidenceLevel
    components: ConfidenceComponentBreakdown
    commercial_risk_penalty: float = Field(ge=0, le=1)
    metrics: ConfidenceEvidenceMetrics
    quality_gate_passed: bool = True
    quality_issues: list[ConfidenceQualityIssue] = Field(default_factory=list)
    analysis_id: str | None = None
    snapshot_id: str | None = None
    product_identity: str | None = None
    registry_id: str | None = None
    registry_revision: int | None = Field(default=None, ge=0)
    input_snapshot_digest: str | None = Field(
        default=None, pattern=r"^snapshot-[0-9a-f]{16}$"
    )
    input_cluster_digest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    provenance_manifest: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    content_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    def expected_content_digest(self) -> str:
        return canonical_digest(
            self.model_dump(mode="json", exclude={"content_digest"})
        )
