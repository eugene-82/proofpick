"""Structured inputs and traceable outputs for source filtering."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.search.models import SearchResult


class SourceType(str, Enum):
    """Minimal deterministic source classification."""

    WEB = "web"
    COMMUNITY = "community"


class DropReason(str, Enum):
    """Deterministic reasons why a source was not accepted."""

    DUPLICATE_URL = "duplicate_url"
    DUPLICATE_CONTENT = "duplicate_content"
    INVALID_URL = "invalid_url"
    EMPTY_CONTENT = "empty_content"


class SourceCandidate(BaseModel):
    """Search result input that can retain an invalid URL for filter reporting."""

    model_config = ConfigDict(str_strip_whitespace=True)

    url: str | None = None
    title: str | None = None
    snippet: str | None = None
    raw_content: str | None = None
    published_at: datetime | None = None
    source_type: SourceType | None = None

    @classmethod
    def from_search_result(cls, result: SearchResult) -> "SourceCandidate":
        return cls(
            url=str(result.url),
            title=result.title,
            snippet=result.snippet,
            raw_content=result.raw_content,
            published_at=result.published_at,
        )


class FilteredSource(BaseModel):
    """Accepted source with provenance and exact-independence metadata."""

    source_key: str = Field(pattern=r"^S\d{3,}$")
    original_url: str
    normalized_url: str
    domain: str
    title: str | None = None
    snippet: str | None = None
    raw_content: str | None = None
    published_at: datetime | None = None
    source_type: SourceType
    content_hash: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    independence_group_id: str = Field(pattern=r"^IG\d{3,}$")


class DroppedSource(BaseModel):
    """Rejected source retained for debugging and observability."""

    source_key: str = Field(pattern=r"^S\d{3,}$")
    original_url: str | None = None
    reason: DropReason
    duplicate_of: str | None = Field(default=None, pattern=r"^S\d{3,}$")
    independence_group_id: str | None = Field(default=None, pattern=r"^IG\d{3,}$")


class SourceFilterResult(BaseModel):
    """Stable partition of accepted and dropped source candidates."""

    accepted_sources: list[FilteredSource] = Field(default_factory=list)
    dropped_sources: list[DroppedSource] = Field(default_factory=list)
