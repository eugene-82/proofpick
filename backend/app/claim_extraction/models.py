"""Validated schemas for reusable source-attributed claims."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.models import ClaimSentiment


class ExtractionModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GroundingState(str, Enum):
    VERIFIED = "VERIFIED"
    UNCERTAIN = "UNCERTAIN"
    REJECTED = "REJECTED"


class SemanticPolarity(str, Enum):
    """Whether the evidence affirms or negates the structured predicate."""

    AFFIRMED = "AFFIRMED"
    NEGATED = "NEGATED"
    UNKNOWN = "UNKNOWN"


class ExperienceType(str, Enum):
    """How directly the experiencer is connected to the observation."""

    DIRECT = "DIRECT"
    REPORTED = "REPORTED"
    SPECULATION = "SPECULATION"
    MARKETING = "MARKETING"
    UNKNOWN = "UNKNOWN"


class ObservationType(str, Enum):
    """Semantic meaning of a duration or observation statement."""

    USAGE = "USAGE"
    OWNERSHIP = "OWNERSHIP"
    TEST = "TEST"
    WARRANTY = "WARRANTY"
    SUBSCRIPTION = "SUBSCRIPTION"
    FIRST_IMPRESSION = "FIRST_IMPRESSION"
    RETURN_PERIOD = "RETURN_PERIOD"
    HYPOTHETICAL = "HYPOTHETICAL"
    UNKNOWN = "UNKNOWN"


class SemanticRelation(ExtractionModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, frozen=True
    )

    """Provider-owned semantic interpretation bound to verbatim evidence."""

    target_product_id: str = Field(min_length=1, max_length=256)
    subject: str = Field(min_length=1, max_length=256)
    predicate: str = Field(min_length=1, max_length=256)
    polarity: SemanticPolarity
    experiencer: str | None = Field(default=None, max_length=256)
    experience_type: ExperienceType
    observation_type: ObservationType
    observation_months: int | None = Field(default=None, ge=1)
    evidence_quote: str = Field(min_length=1, max_length=2_000)
    evidence_source_id: str = Field(pattern=r"^S\d{3,}$")
    verification_status: GroundingState


class ExtractedClaim(ExtractionModel):
    """One product-use claim grounded in a short source fragment."""

    source_id: str = Field(pattern=r"^S\d{3,}$")
    aspect: str = Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_]*$")
    claim: str = Field(min_length=1, max_length=1_000)
    sentiment: ClaimSentiment
    severity: int = Field(ge=1, le=5)
    usage_period_months: int | None = Field(ge=1)
    evidence_fragment: str = Field(min_length=1, max_length=500)

    semantic_relation: SemanticRelation | None = None

class ClaimExtractionPayload(ExtractionModel):
    """Provider output schema for one evidence batch."""

    claims: list[ExtractedClaim]


class GroundingReasonCode(str, Enum):
    VERIFIED = "VERIFIED"
    SOURCE_MISMATCH = "SOURCE_MISMATCH"
    FRAGMENT_NOT_FOUND = "FRAGMENT_NOT_FOUND"
    TINY_FRAGMENT = "TINY_FRAGMENT"
    CLAIM_NOT_SUPPORTED = "CLAIM_NOT_SUPPORTED"
    NEGATION_MISMATCH = "NEGATION_MISMATCH"
    POLARITY_MISMATCH = "POLARITY_MISMATCH"
    THIRD_PARTY_REPORT = "THIRD_PARTY_REPORT"
    NON_EXPERIENCE = "NON_EXPERIENCE"
    SPECULATION = "SPECULATION"
    USAGE_PERIOD_MISMATCH = "USAGE_PERIOD_MISMATCH"
    PRODUCT_IDENTITY_MISMATCH = "PRODUCT_IDENTITY_MISMATCH"
    SUBJECT_PREDICATE_MISMATCH = "SUBJECT_PREDICATE_MISMATCH"
    UNSAFE_PARTIAL_EVIDENCE = "UNSAFE_PARTIAL_EVIDENCE"
    USAGE_PERIOD_DROPPED = "USAGE_PERIOD_DROPPED"

    SEMANTIC_UNCERTAIN = "SEMANTIC_UNCERTAIN"
    SEMANTIC_REJECTED = "SEMANTIC_REJECTED"
    VERIFICATION_BINDING_MISMATCH = "VERIFICATION_BINDING_MISMATCH"

class GroundingAssessment(ExtractionModel):
    """Traceable decision about whether one extracted claim may drive decisions."""


    claim: ExtractedClaim
    state: GroundingState
    reason_code: GroundingReasonCode
    detail: str = Field(min_length=1)
    metadata_issues: list[GroundingReasonCode] = Field(default_factory=list)
    semantic_relation: SemanticRelation | None = None


class ClaimVerificationVerdict(ExtractionModel):
    """One verifier result, explicitly bound to its input candidate."""

    claim: ExtractedClaim
    relation: SemanticRelation | None = None
    verification_status: GroundingState
    detail: str = Field(min_length=1)


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
    """Verified claims, assessments, and explicit batch failures."""

    claims: list[ExtractedClaim] = Field(default_factory=list)
    grounding_assessments: list[GroundingAssessment] = Field(default_factory=list)
    failures: list[ClaimExtractionFailure] = Field(default_factory=list)
