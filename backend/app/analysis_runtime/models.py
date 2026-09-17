"""Minimal synchronous API models for the demo analysis path."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator

from app.confidence.models import ConfidenceLevel
from app.decision.models import DecisionReasonCode, DecisionSignal
from app.models import AnalysisStatus, ClaimSentiment, PurchaseDecision


class RuntimeModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AnalysisRequest(RuntimeModel):
    query: str = Field(min_length=1, max_length=500)

    @field_validator("query")
    @classmethod
    def reject_blank_query(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("query must not be blank")
        return value


class AnalysisEvidenceReference(RuntimeModel):
    source_id: str = Field(pattern=r"^S\d{3,}$")
    source_url: HttpUrl
    fragment: str = Field(min_length=1, max_length=500)


class AnalysisClaimSummary(RuntimeModel):
    cluster_id: str = Field(pattern=r"^CL\d{3,}$")
    canonical_claim: str = Field(min_length=1)
    aspect: str = Field(min_length=1)
    sentiment: ClaimSentiment
    max_severity: int = Field(ge=1, le=5)
    independent_source_count: int = Field(ge=0)
    evidence: list[AnalysisEvidenceReference]


class AnalysisSourceSummary(RuntimeModel):
    source_id: str = Field(pattern=r"^S\d{3,}$")
    url: HttpUrl
    domain: str = Field(min_length=1)
    title: str | None = None
    independence_group_id: str = Field(pattern=r"^IG\d{3,}$")


class AnalysisResponse(RuntimeModel):
    analysis_id: UUID
    status: AnalysisStatus
    product: str = Field(min_length=1)
    initial_decision: PurchaseDecision
    decision: PurchaseDecision
    confidence: float = Field(ge=0, le=1)
    confidence_level: ConfidenceLevel
    reasons: list[DecisionReasonCode]
    blocking_issues: list[DecisionSignal]
    unresolved_risks: list[DecisionSignal]
    counter_evidence_attempted: bool
    counter_evidence_completed: bool
    counter_evidence_queries: list[str] = Field(max_length=3)
    counter_evidence_source_count: int = Field(ge=0)
    counter_evidence_sources: list[AnalysisSourceSummary]
    decision_changed: bool
    claims: list[AnalysisClaimSummary]
    sources: list[AnalysisSourceSummary]
