"""Structured, bounded evidence passed to later claim extraction."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

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
