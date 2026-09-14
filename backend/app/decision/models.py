"""Structured and reusable purchase-decision outputs."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models import ClaimSentiment, PurchaseDecision


class DecisionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class DecisionReasonCode(str, Enum):
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    LOW_EVIDENCE_CONFIDENCE = "LOW_EVIDENCE_CONFIDENCE"
    INSUFFICIENT_INDEPENDENT_EVIDENCE = "INSUFFICIENT_INDEPENDENT_EVIDENCE"
    NO_MEANINGFUL_CLAIMS = "NO_MEANINGFUL_CLAIMS"
    REPEATED_HIGH_SEVERITY_ISSUE = "REPEATED_HIGH_SEVERITY_ISSUE"
    CONDITIONAL_NEGATIVE_ISSUE = "CONDITIONAL_NEGATIVE_ISSUE"
    LONG_TERM_NEGATIVE_ISSUE = "LONG_TERM_NEGATIVE_ISSUE"
    STRONG_POSITIVE_SUPPORT = "STRONG_POSITIVE_SUPPORT"
    CONFLICTING_EVIDENCE = "CONFLICTING_EVIDENCE"
    NO_BLOCKING_ISSUES = "NO_BLOCKING_ISSUES"


class DecisionSignal(DecisionModel):
    reason_code: DecisionReasonCode
    cluster_id: str = Field(pattern=r"^CL\d{3,}$")
    aspect: str = Field(min_length=1)
    sentiment: ClaimSentiment
    severity: float = Field(ge=1, le=5)
    max_severity: int = Field(ge=1, le=5)
    source_count: int = Field(ge=1)
    independent_source_count: int = Field(ge=1)
    domain_count: int = Field(ge=1)
    long_term_evidence: bool


class PurchaseDecisionResult(DecisionModel):
    decision: PurchaseDecision
    confidence_score: float = Field(ge=0, le=1)
    reasons: list[DecisionReasonCode] = Field(min_length=1)
    blocking_issues: list[DecisionSignal] = Field(default_factory=list)
    conditions: list[DecisionSignal] = Field(default_factory=list)
    supporting_signals: list[DecisionSignal] = Field(default_factory=list)
    evidence_sufficient: bool
    should_find_alternatives: bool

    @model_validator(mode="after")
    def validate_decision_invariants(self) -> "PurchaseDecisionResult":
        if self.decision is PurchaseDecision.BUY_IF and not self.conditions:
            raise ValueError("BUY_IF requires at least one condition")
        if self.decision is PurchaseDecision.SKIP and not self.blocking_issues:
            raise ValueError("SKIP requires at least one blocking issue")
        expected_alternatives = self.decision is PurchaseDecision.SKIP
        if self.should_find_alternatives is not expected_alternatives:
            raise ValueError("alternative trigger must match a SKIP decision")
        expected_sufficient = self.decision is not PurchaseDecision.EARLY_ADOPTER
        if self.evidence_sufficient is not expected_sufficient:
            raise ValueError("only EARLY_ADOPTER may have insufficient evidence")
        return self
