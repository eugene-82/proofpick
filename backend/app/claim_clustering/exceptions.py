"""Claim clustering and embedding errors."""


class ClaimClusteringError(RuntimeError):
    """Base claim clustering error."""


class SourceMetadataError(ClaimClusteringError):
    """Required source provenance is missing or ambiguous."""


class EmbeddingProviderError(ClaimClusteringError):
    """Embedding provider request failed."""


class EmbeddingProviderTimeoutError(EmbeddingProviderError):
    """Embedding provider timed out."""


class EmbeddingProviderRateLimitError(EmbeddingProviderError):
    """Embedding provider rate limit was reached."""


class EmbeddingProviderConfigurationError(EmbeddingProviderError):
    """Embedding provider configuration is missing or invalid."""


class EmbeddingValidationError(ClaimClusteringError):
    """Embedding vectors were malformed or unusable."""
