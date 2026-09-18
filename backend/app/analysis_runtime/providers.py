"""Request-time construction of runtime provider interfaces."""

import os
from dataclasses import dataclass

from app.claim_clustering.base import EmbeddingProvider
from app.claim_clustering.exceptions import EmbeddingProviderConfigurationError
from app.claim_clustering.openai_provider import (
    DEFAULT_OPENAI_EMBEDDING_MODEL,
    OpenAIEmbeddingProvider,
)
from app.claim_extraction.base import ClaimExtractionProvider
from app.claim_extraction.exceptions import ClaimProviderConfigurationError
from app.claim_extraction.openai_provider import (
    OpenAIClaimExtractionProvider,
)
from app.claim_extraction.verification import (
    ClaimVerificationProvider,
    EmbeddedClaimVerificationProvider,
)
from app.search.base import SearchProvider
from app.search.tavily import TavilySearchProvider

from .exceptions import AnalysisProviderUnavailableError


@dataclass(frozen=True)
class AnalysisRuntimeProviders:
    search: SearchProvider
    claim_extraction: ClaimExtractionProvider
    claim_verification: ClaimVerificationProvider
    embeddings: EmbeddingProvider

    @classmethod
    def from_env(cls) -> "AnalysisRuntimeProviders":
        """Build live providers lazily; importing the application is always safe."""

        tavily_key = os.getenv("TAVILY_API_KEY", "").strip()
        openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not tavily_key or not openai_key:
            raise AnalysisProviderUnavailableError(
                "required analysis providers are not configured"
            )

        try:
            extraction = OpenAIClaimExtractionProvider.from_env()
            embeddings = OpenAIEmbeddingProvider(
                api_key=openai_key,
                model=os.getenv(
                    "OPENAI_EMBEDDING_MODEL", DEFAULT_OPENAI_EMBEDDING_MODEL
                ),
            )
        except (
            ClaimProviderConfigurationError,
            EmbeddingProviderConfigurationError,
        ) as error:
            raise AnalysisProviderUnavailableError(
                "analysis model provider configuration is invalid"
            ) from error

        return cls(
            search=TavilySearchProvider(api_key=tavily_key),
            claim_extraction=extraction,
            claim_verification=EmbeddedClaimVerificationProvider(),
            embeddings=embeddings,
        )
