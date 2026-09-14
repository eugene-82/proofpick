"""Centralized, configurable confidence policy."""

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ConfidencePolicy(BaseModel):
    """Weights and saturation constants for the initial MVP heuristic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_volume_weight: float = Field(default=0.18, ge=0, le=1)
    independence_weight: float = Field(default=0.28, ge=0, le=1)
    diversity_weight: float = Field(default=0.15, ge=0, le=1)
    agreement_weight: float = Field(default=0.27, ge=0, le=1)
    long_term_weight: float = Field(default=0.12, ge=0, le=1)
    commercial_risk_weight: float = Field(default=0.10, ge=0, le=1)

    volume_saturation_scale: float = Field(default=5.0, gt=0)
    independence_saturation_scale: float = Field(default=4.0, gt=0)
    diversity_saturation_scale: float = Field(default=3.0, gt=0)
    agreement_saturation_scale: float = Field(default=2.5, gt=0)
    long_term_saturation_scale: float = Field(default=3.0, gt=0)
    long_term_threshold_months: int = Field(default=6, ge=1)
    long_term_target_months: int = Field(default=12, ge=1)

    independence_absolute_share: float = Field(default=0.75, ge=0, le=1)
    long_term_absolute_share: float = Field(default=0.50, ge=0, le=1)
    long_term_coverage_share: float = Field(default=0.30, ge=0, le=1)
    long_term_duration_share: float = Field(default=0.20, ge=0, le=1)

    medium_threshold: float = Field(default=0.40, ge=0, le=1)
    high_threshold: float = Field(default=0.70, ge=0, le=1)
    single_independent_source_cap: float = Field(default=0.39, ge=0, le=1)

    @model_validator(mode="after")
    def validate_policy(self) -> "ConfidencePolicy":
        positive_weights = (
            self.evidence_volume_weight,
            self.independence_weight,
            self.diversity_weight,
            self.agreement_weight,
            self.long_term_weight,
        )
        if abs(sum(positive_weights) - 1.0) > 1e-9:
            raise ValueError("positive confidence weights must sum to 1")
        if not self.medium_threshold < self.high_threshold:
            raise ValueError("medium_threshold must be lower than high_threshold")
        if self.single_independent_source_cap >= self.medium_threshold:
            raise ValueError("single-source cap must remain below the medium threshold")
        if abs(
            self.long_term_absolute_share
            + self.long_term_coverage_share
            + self.long_term_duration_share
            - 1.0
        ) > 1e-9:
            raise ValueError("long-term shares must sum to 1")
        return self
