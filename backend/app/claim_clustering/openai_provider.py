"""Minimal OpenAI embeddings provider using the existing HTTP client."""

import os
from collections.abc import Sequence
from typing import Any

import httpx

from .base import EmbeddingProvider
from .exceptions import (
    EmbeddingProviderConfigurationError,
    EmbeddingProviderError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderTimeoutError,
    EmbeddingValidationError,
)


DEFAULT_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_EMBEDDINGS_URL = "https://api.openai.com/v1/embeddings"


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """Batch compact claim strings through the OpenAI embeddings endpoint."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_EMBEDDING_MODEL,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key.strip():
            raise EmbeddingProviderConfigurationError("OPENAI_API_KEY is required")
        if not model.strip():
            raise EmbeddingProviderConfigurationError("OPENAI_EMBEDDING_MODEL is required")
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_env(cls) -> "OpenAIEmbeddingProvider":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_EMBEDDING_MODEL", DEFAULT_OPENAI_EMBEDDING_MODEL),
        )

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise EmbeddingValidationError("embedding input text must not be empty")

        try:
            response = self._client.post(
                OPENAI_EMBEDDINGS_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "input": list(texts),
                    "model": self._model,
                    "encoding_format": "float",
                },
            )
        except httpx.TimeoutException as error:
            raise EmbeddingProviderTimeoutError("OpenAI embedding request timed out") from error
        except httpx.RequestError as error:
            raise EmbeddingProviderError("OpenAI embedding request failed") from error

        if response.status_code == 429:
            raise EmbeddingProviderRateLimitError("OpenAI embedding rate limit reached")
        if response.is_error:
            raise EmbeddingProviderError(
                f"OpenAI embedding request failed with HTTP {response.status_code}"
            )

        try:
            response_data: dict[str, Any] = response.json()
            data = response_data["data"]
            indexed_vectors = {
                item["index"]: item["embedding"]
                for item in data
                if isinstance(item, dict)
            }
            if set(indexed_vectors) != set(range(len(texts))):
                raise ValueError("embedding indices do not match input")
            return [indexed_vectors[index] for index in range(len(texts))]
        except (KeyError, TypeError, ValueError) as error:
            raise EmbeddingValidationError("OpenAI returned malformed embeddings") from error
