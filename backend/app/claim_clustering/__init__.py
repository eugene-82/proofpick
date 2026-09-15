"""Semantic claim clustering with deterministic provenance aggregation."""
from .base import EmbeddingProvider
from .exceptions import (
    ClaimClusteringError, EmbeddingProviderConfigurationError, EmbeddingProviderError,
    EmbeddingProviderRateLimitError, EmbeddingProviderTimeoutError,
    EmbeddingValidationError, SourceMetadataError,
)
from .models import ClaimCluster, ClaimClusteringResult, ClusterMember
from .openai_provider import OpenAIEmbeddingProvider
from .policy import ClaimClusteringPolicy
from .service import SemanticClaimClusterer
from .similarity import cosine_similarity, normalize_vector
from .snapshot import EvaluationSnapshot, SnapshotContractError
__all__ = [
    "ClaimCluster", "ClaimClusteringError", "ClaimClusteringPolicy",
    "ClaimClusteringResult", "ClusterMember", "EmbeddingProvider",
    "EmbeddingProviderConfigurationError", "EmbeddingProviderError",
    "EmbeddingProviderRateLimitError", "EmbeddingProviderTimeoutError",
    "EmbeddingValidationError", "EvaluationSnapshot", "OpenAIEmbeddingProvider",
    "SemanticClaimClusterer", "SnapshotContractError", "SourceMetadataError",
    "cosine_similarity", "normalize_vector",
]
