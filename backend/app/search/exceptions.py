"""Errors exposed by the provider-neutral search layer."""


class SearchProviderError(RuntimeError):
    """Base error for a failed search provider request."""


class SearchTimeoutError(SearchProviderError):
    """The search provider did not respond before the configured timeout."""


class SearchRateLimitError(SearchProviderError):
    """The search provider rejected the request because of rate limiting."""


class SearchResponseError(SearchProviderError):
    """The provider returned a response that cannot be normalized safely."""
