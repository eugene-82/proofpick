"""Normalized provider-independent search result models."""

from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, HttpUrl, field_validator, model_validator


class SearchResult(BaseModel):
    """A compact result passed from search providers to later pipeline stages."""

    model_config = ConfigDict(str_strip_whitespace=True)

    title: str | None = None
    url: HttpUrl
    snippet: str | None = None
    domain: str = ""
    published_at: datetime | None = None
    raw_content: str | None = None

    @field_validator("published_at", mode="before")
    @classmethod
    def normalize_published_at(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        return value

    @model_validator(mode="after")
    def normalize_domain(self) -> "SearchResult":
        host = self.url.host
        if host is None:
            raise ValueError("url must include a host")

        self.domain = host.lower().removeprefix("www.")
        return self
