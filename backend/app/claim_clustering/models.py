"""Structured claim cluster output with complete provenance."""

from pydantic import BaseModel, ConfigDict, Field

from app.claim_extraction.models import ExtractedClaim
from app.models import ClaimSentiment


class ClusteringModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ClusterMember(ClusteringModel):
    """A stable temporary claim identity and its validated source claim."""

    claim_id: str = Field(pattern=r"^C\d{3,}$")
    claim: ExtractedClaim
    embedding_key: str = Field(pattern=r"^[0-9a-f]{64}$")


class ClaimCluster(ClusteringModel):
    """Semantically related claims and deterministic evidence aggregates."""

    cluster_id: str = Field(pattern=r"^CL\d{3,}$")
    canonical_claim: str = Field(min_length=1)
    aspect: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    sentiment: ClaimSentiment
    members: list[ClusterMember] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    source_count: int = Field(ge=1)
    independence_group_ids: list[str] = Field(min_length=1)
    independent_source_count: int = Field(ge=1)
    domains: list[str] = Field(min_length=1)
    domain_count: int = Field(ge=1)
    average_severity: float = Field(ge=1, le=5)
    max_severity: int = Field(ge=1, le=5)
    usage_period_months: list[int] = Field(default_factory=list)


class ClaimClusteringResult(ClusteringModel):
    """Stable ordered clusters for downstream confidence evaluation."""

    clusters: list[ClaimCluster] = Field(default_factory=list)
