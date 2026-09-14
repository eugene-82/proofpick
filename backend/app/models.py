"""Core domain models shared by ProofPick's API and persistence layers."""

from enum import Enum
from typing import Annotated
from uuid import UUID

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    model_validator,
)


NonEmptyString = Annotated[str, Field(min_length=1)]
UnitInterval = Annotated[float, Field(ge=0, le=1)]


class AnalysisStatus(str, Enum):
    QUEUED = "queued"
    RESOLVING_PRODUCT = "resolving_product"
    SEARCHING = "searching"
    FILTERING_SOURCES = "filtering_sources"
    EXTRACTING_CLAIMS = "extracting_claims"
    CLUSTERING_CLAIMS = "clustering_claims"
    EVALUATING = "evaluating"
    SEARCHING_COUNTER_EVIDENCE = "searching_counter_evidence"
    FINDING_ALTERNATIVES = "finding_alternatives"
    VERIFYING_ALTERNATIVES = "verifying_alternatives"
    COMPLETE = "complete"
    FAILED = "failed"


class PurchaseDecision(str, Enum):
    BUY = "BUY"
    BUY_IF = "BUY_IF"
    SKIP = "SKIP"
    EARLY_ADOPTER = "EARLY_ADOPTER"


class ClaimSentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class DomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class ProductBase(DomainModel):
    brand: NonEmptyString | None = None
    name: NonEmptyString
    model: NonEmptyString | None = None
    generation: NonEmptyString | None = None
    category: NonEmptyString | None = None
    canonical_name: NonEmptyString


class ProductCreate(ProductBase):
    pass


class ProductRead(ProductBase):
    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime


class AnalysisBase(DomainModel):
    product_id: UUID
    status: AnalysisStatus = AnalysisStatus.QUEUED
    decision: PurchaseDecision | None = None
    confidence: UnitInterval | None = None
    summary: NonEmptyString | None = None
    pipeline_version: NonEmptyString = "v1"


class AnalysisCreate(AnalysisBase):
    pass


class AnalysisRead(AnalysisBase):
    id: UUID
    created_at: AwareDatetime
    updated_at: AwareDatetime
    completed_at: AwareDatetime | None = None


class SourceBase(DomainModel):
    analysis_id: UUID
    source_code: Annotated[str, Field(pattern=r"^S\d{3,}$")]
    url: HttpUrl
    normalized_url: HttpUrl
    domain: NonEmptyString
    title: NonEmptyString | None = None
    source_type: NonEmptyString | None = None
    published_at: AwareDatetime | None = None
    commercial_signal: UnitInterval = 0
    quality_score: UnitInterval = 0
    content_hash: NonEmptyString | None = None
    independent_group_id: NonEmptyString | None = None


class SourceCreate(SourceBase):
    pass


class SourceRead(SourceBase):
    id: UUID
    created_at: AwareDatetime


class ClaimBase(DomainModel):
    analysis_id: UUID
    claim_code: Annotated[str, Field(pattern=r"^C\d{3,}$")]
    aspect: NonEmptyString
    canonical_claim: NonEmptyString
    sentiment: ClaimSentiment
    severity: Annotated[int, Field(ge=1, le=5)]
    source_count: Annotated[int, Field(ge=0)] = 0
    independent_source_count: Annotated[int, Field(ge=0)] = 0
    platform_count: Annotated[int, Field(ge=0)] = 0
    confidence: UnitInterval | None = None

    @model_validator(mode="after")
    def validate_source_counts(self) -> "ClaimBase":
        if self.independent_source_count > self.source_count:
            raise ValueError("independent_source_count cannot exceed source_count")
        return self


class ClaimCreate(ClaimBase):
    pass


class ClaimRead(ClaimBase):
    id: UUID
    created_at: AwareDatetime


class ClaimSourceBase(DomainModel):
    claim_id: UUID
    source_id: UUID
    evidence: NonEmptyString
    usage_period_months: Annotated[int, Field(ge=0)] | None = None


class ClaimSourceCreate(ClaimSourceBase):
    pass


class ClaimSourceRead(ClaimSourceBase):
    created_at: AwareDatetime


class AlternativeBase(DomainModel):
    analysis_id: UUID
    alternative_product_id: UUID
    alternative_analysis_id: UUID
    rank: Annotated[int, Field(ge=1)]
    reason: NonEmptyString


class AlternativeCreate(AlternativeBase):
    pass


class AlternativeRead(AlternativeBase):
    id: UUID
    created_at: AwareDatetime
