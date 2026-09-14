"""Tavily-specific implementation of the search provider interface."""

import os
from collections.abc import Mapping
from typing import Any

import httpx
from pydantic import ValidationError

from .base import SearchProvider
from .exceptions import (
    SearchProviderError,
    SearchRateLimitError,
    SearchResponseError,
    SearchTimeoutError,
)
from .models import SearchResult


class TavilySearchProvider(SearchProvider):
    """Normalize Tavily Search API responses without exposing them to callers."""

    endpoint = "https://api.tavily.com/search"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_seconds: float = 10.0,
        client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("TAVILY_API_KEY")
        self._timeout_seconds = timeout_seconds
        self._client = client

    def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        include_raw_content: bool = False,
    ) -> list[SearchResult]:
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("query must not be empty")
        if max_results < 1:
            raise ValueError("max_results must be at least 1")
        if not self._api_key:
            raise SearchProviderError("Tavily API key is not configured")

        payload = {
            "api_key": self._api_key,
            "query": normalized_query,
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": include_raw_content,
        }
        response = self._post(payload)

        if response.status_code == 429:
            raise SearchRateLimitError("Tavily search request was rate limited")
        if response.is_error:
            raise SearchProviderError(
                f"Tavily search request failed with HTTP {response.status_code}"
            )

        try:
            body = response.json()
        except ValueError as exc:
            raise SearchResponseError("Tavily returned invalid JSON") from exc

        if not isinstance(body, Mapping):
            raise SearchResponseError("Tavily response must be a JSON object")

        raw_results = body.get("results")
        if not isinstance(raw_results, list):
            raise SearchResponseError("Tavily response results must be a list")

        return [self._normalize_result(item) for item in raw_results]

    def _post(self, payload: dict[str, Any]) -> httpx.Response:
        try:
            if self._client is not None:
                return self._client.post(self.endpoint, json=payload)

            with httpx.Client(timeout=self._timeout_seconds) as client:
                return client.post(self.endpoint, json=payload)
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError("Tavily search request timed out") from exc
        except httpx.RequestError as exc:
            raise SearchProviderError("Tavily search request failed") from exc

    @staticmethod
    def _normalize_result(raw_result: object) -> SearchResult:
        if not isinstance(raw_result, Mapping):
            raise SearchResponseError("Tavily result must be a JSON object")

        try:
            return SearchResult(
                title=raw_result.get("title"),
                url=raw_result.get("url"),
                snippet=raw_result.get("content"),
                published_at=raw_result.get("published_date"),
                raw_content=raw_result.get("raw_content"),
            )
        except (TypeError, ValueError, ValidationError) as exc:
            raise SearchResponseError("Tavily result has an invalid shape") from exc
