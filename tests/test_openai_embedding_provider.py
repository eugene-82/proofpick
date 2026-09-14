import json

import httpx
import pytest

from app.claim_clustering import (
    EmbeddingProviderConfigurationError,
    EmbeddingProviderError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderTimeoutError,
    EmbeddingValidationError,
    OpenAIEmbeddingProvider,
)


def test_openai_embedding_provider_batches_inputs_without_live_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url == httpx.URL("https://api.openai.com/v1/embeddings")
        assert request.headers["authorization"] == "Bearer test-key"
        assert body == {
            "input": ["battery | first", "noise | second"],
            "model": "text-embedding-3-small",
            "encoding_format": "float",
        }
        return httpx.Response(
            200,
            json={
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ]
            },
        )

    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.embed(["battery | first", "noise | second"]) == [
        [1.0, 0.0],
        [0.0, 1.0],
    ]


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (429, EmbeddingProviderRateLimitError),
        (500, EmbeddingProviderError),
    ],
)
def test_openai_embedding_provider_maps_http_errors(
    status_code: int, error_type: type[Exception]
) -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(status_code, json={"error": "failed"})
            )
        ),
    )

    with pytest.raises(error_type):
        provider.embed(["battery | claim"])


def test_openai_embedding_provider_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    with pytest.raises(EmbeddingProviderTimeoutError):
        provider.embed(["battery | claim"])


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"data": []},
        {"data": [{"index": 2, "embedding": [1.0, 0.0]}]},
        {"data": [{"index": 0}]},
    ],
)
def test_openai_embedding_provider_rejects_malformed_response(payload: dict) -> None:
    provider = OpenAIEmbeddingProvider(
        api_key="test-key",
        client=httpx.Client(
            transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload))
        ),
    )

    with pytest.raises(EmbeddingValidationError):
        provider.embed(["battery | claim"])


def test_openai_embedding_provider_requires_key_and_nonempty_input() -> None:
    with pytest.raises(EmbeddingProviderConfigurationError):
        OpenAIEmbeddingProvider(api_key="")

    provider = OpenAIEmbeddingProvider(api_key="test-key")
    assert provider.embed([]) == []
    with pytest.raises(EmbeddingValidationError):
        provider.embed([" "])
