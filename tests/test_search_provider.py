import json

import httpx
import pytest
from pydantic import ValidationError

from app.search import (
    SearchProviderError,
    SearchRateLimitError,
    SearchResponseError,
    SearchResult,
    SearchTimeoutError,
    TavilySearchProvider,
)


def make_provider(handler: httpx.MockTransport) -> TavilySearchProvider:
    client = httpx.Client(transport=handler)
    return TavilySearchProvider(api_key="test-key", client=client)


def test_tavily_provider_normalizes_successful_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert request.url == httpx.URL("https://api.tavily.com/search")
        assert payload == {
            "api_key": "test-key",
            "query": "wireless headphones",
            "max_results": 2,
            "include_answer": False,
            "include_raw_content": True,
        }
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "Example review",
                        "url": "https://WWW.Example.com/review",
                        "content": "A concise review excerpt.",
                        "published_date": "2025-01-15",
                        "raw_content": "Full source content.",
                    }
                ]
            },
        )

    results = make_provider(httpx.MockTransport(handler)).search(
        " wireless headphones ", max_results=2, include_raw_content=True
    )

    assert len(results) == 1
    assert results[0].domain == "example.com"
    assert results[0].snippet == "A concise review excerpt."
    assert results[0].raw_content == "Full source content."
    assert results[0].published_at is not None
    assert results[0].published_at.tzinfo is not None


def test_tavily_provider_returns_empty_results() -> None:
    provider = make_provider(
        httpx.MockTransport(lambda _: httpx.Response(200, json={"results": []}))
    )

    assert provider.search("wireless headphones") == []


def test_tavily_provider_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    with pytest.raises(SearchTimeoutError):
        make_provider(httpx.MockTransport(handler)).search("wireless headphones")


def test_tavily_provider_maps_network_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    with pytest.raises(SearchProviderError):
        make_provider(httpx.MockTransport(handler)).search("wireless headphones")


def test_tavily_provider_maps_rate_limit() -> None:
    provider = make_provider(
        httpx.MockTransport(lambda _: httpx.Response(429, json={}))
    )

    with pytest.raises(SearchRateLimitError):
        provider.search("wireless headphones")


def test_tavily_provider_rejects_malformed_results() -> None:
    provider = make_provider(
        httpx.MockTransport(
            lambda _: httpx.Response(
                200, json={"results": [{"title": "Missing URL"}]}
            )
        )
    )

    with pytest.raises(SearchResponseError):
        provider.search("wireless headphones")


def test_search_result_normalizes_domain_and_requires_url() -> None:
    result = SearchResult(url="https://www.Example.com/path", title=None, snippet=None)

    assert result.domain == "example.com"
    assert result.published_at is None
    assert result.raw_content is None

    with pytest.raises(ValidationError):
        SearchResult(url="not a URL")
