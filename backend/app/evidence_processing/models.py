"""Structured, bounded evidence passed to later claim extraction."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.source_filtering.models import IndependenceState, SourceType


class EvidenceSource(str, Enum):
    RAW_CONTENT = "raw_content"
    SNIPPET = "snippet"


class EvidenceQuality(str, Enum):
    FULL_CONTENT = "full_content"
    PARTIAL_CONTENT = "partial_content"
    SNIPPET_ONLY = "snippet_only"
    UNKNOWN = "unknown"


class ObservationState(str, Enum):
    ESTABLISHED = "established"
    FIRST_IMPRESSION = "first_impression"
    UNKNOWN = "unknown"


class EvidenceSegment(BaseModel):
    """One extractive evidence span with explicit decision eligibility."""

    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, frozen=True
    )

    text: str = Field(min_length=1)
    complete: bool
    truncated: bool
    grounding_eligible: bool
    original_start: int | None = Field(default=None, ge=0)
    original_end: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_segment_contract(self) -> "EvidenceSegment":
        if self.grounding_eligible and (not self.complete or self.truncated):
            raise ValueError(
                "grounding-eligible evidence must be complete and untruncated"
            )
        if (self.original_start is None) is not (self.original_end is None):
            raise ValueError("segment offsets must be provided together")
        if (
            self.original_start is not None
            and self.original_end is not None
            and self.original_end <= self.original_start
        ):
            raise ValueError("segment end must be greater than segment start")
        return self


class EvidenceDocument(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source_key: str = Field(pattern=r"^S\d{3,}$")
    original_url: str
    normalized_url: str
    domain: str
    title: str | None = None
    text: str = Field(min_length=1)
    evidence_source: EvidenceSource
    original_length: int = Field(ge=0)
    compressed_length: int = Field(ge=0)
    compression_ratio: float = Field(ge=0, le=1)
    truncated: bool
    content_hash: str | None = None
    source_type: SourceType
    independence_group_id: str = Field(pattern=r"^IG\d{3,}$")
    independence_state: IndependenceState = IndependenceState.UNKNOWN
    evidence_quality: EvidenceQuality = EvidenceQuality.UNKNOWN
    observation_state: ObservationState = ObservationState.UNKNOWN
    content_coverage_ratio: float = Field(default=0, ge=0, le=1)
    grounding_text: str | None = None
    grounding_eligible: bool = True
    segments: tuple[EvidenceSegment, ...] = ()
    evidence_coverage_limited: bool = False
