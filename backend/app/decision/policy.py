"""Centralized MVP heuristics for deterministic purchase decisions."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DecisionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    minimum_evidence_confidence: float = Field(default=0.40, ge=0, le=1)
    minimum_independent_sources: int = Field(default=3, ge=1)
    skip_min_independent_support: int = Field(default=4, ge=2)
    skip_min_severity: int = Field(default=4, ge=1, le=5)
    buy_if_min_independent_support: int = Field(default=2, ge=2)
    buy_if_min_severity: int = Field(default=2, ge=1, le=5)
    positive_min_independent_support: int = Field(default=2, ge=2)
    conflict_min_independent_support: int = Field(default=2, ge=1)
    long_term_threshold_months: int = Field(default=6, ge=1)

    @model_validator(mode="after")
    def validate_threshold_order(self) -> "DecisionPolicy":
        if self.skip_min_independent_support < self.buy_if_min_independent_support:
            raise ValueError("SKIP support threshold cannot be below BUY_IF threshold")
        if self.skip_min_severity < self.buy_if_min_severity:
            raise ValueError("SKIP severity threshold cannot be below BUY_IF threshold")
        return self
