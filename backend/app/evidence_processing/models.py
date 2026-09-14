"""Structured, bounded evidence passed to later claim extraction."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.source_filtering.models import SourceType


class EvidenceSource(str, Enum):
    """Which source field supplied the evidence text."""

    RAW_CONTENT = "raw_content"
    SNIPPET = "snippet"


class EvidenceDocument(BaseModel):
    """Extractive evidence with preserved source provenance and metrics."""

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
