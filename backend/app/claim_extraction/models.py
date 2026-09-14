"""Validated schemas for reusable source-attributed claims."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.models import ClaimSentiment


class ExtractionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ExtractedClaim(ExtractionModel):
    """One product-use claim grounded in a short source fragment."""

    source_id: str = Field(pattern=r"^S\d{3,}$")
    aspect: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    claim: str = Field(min_length=1, max_length=1_000)
    sentiment: ClaimSentiment
    severity: int = Field(ge=1, le=5)
    usage_period_months: int | None = Field(ge=1)
    evidence_fragment: str = Field(min_length=1, max_length=500)


class ClaimExtractionPayload(ExtractionModel):
    """Provider output schema for one evidence batch."""

    claims: list[ExtractedClaim]


class ExtractionFailureCode(str, Enum):
    PROVIDER_ERROR = "provider_error"
    MALFORMED_OUTPUT = "malformed_output"
    GROUNDING_ERROR = "grounding_error"


class ClaimExtractionFailure(ExtractionModel):
    """Traceable failure for a batch whose output was not accepted."""

    batch_index: int = Field(ge=1)
    source_ids: list[str]
    code: ExtractionFailureCode
    message: str = Field(min_length=1)


class ClaimExtractionResult(ExtractionModel):
    """Claims and explicit failures across all processed batches."""

    claims: list[ExtractedClaim] = Field(default_factory=list)
    failures: list[ClaimExtractionFailure] = Field(default_factory=list)
