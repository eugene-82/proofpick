"""Structured claim cluster output with complete provenance."""

from pydantic import BaseModel, ConfigDict, Field
from app.claim_extraction.models import ExtractedClaim
from app.models import ClaimSentiment
from app.source_filtering.models import IndependenceState

class ClusteringModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class ClusterMember(ClusteringModel):
    claim_id: str = Field(pattern=r"^C\d{3,}$")
    claim: ExtractedClaim
    embedding_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    independence_group_id: str | None = Field(default=None, pattern=r"^IG\d{3,}$")
    independence_state: IndependenceState = IndependenceState.UNKNOWN

class ClaimCluster(ClusteringModel):
    cluster_id: str = Field(pattern=r"^CL\d{3,}$")
    canonical_claim: str = Field(min_length=1)
    aspect: str = Field(min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    sentiment: ClaimSentiment
    members: list[ClusterMember] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    source_count: int = Field(ge=1)
    independence_group_ids: list[str] = Field(min_length=1)
    confirmed_independence_group_ids: list[str] | None = None
    unknown_independence_group_ids: list[str] | None = None
    independent_source_count: int = Field(ge=0)
    domains: list[str] = Field(min_length=1)
    domain_count: int = Field(ge=1)
    average_severity: float = Field(ge=1, le=5)
    max_severity: int = Field(ge=1, le=5)
    usage_period_months: list[int] = Field(default_factory=list)

class ClaimClusteringResult(ClusteringModel):
    clusters: list[ClaimCluster] = Field(default_factory=list)
    analysis_id: str | None = None
    snapshot_id: str | None = None
    product_identity: str | None = None
    registry_id: str | None = None
    registry_revision: int | None = Field(default=None, ge=0)
