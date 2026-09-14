"""Claim extraction errors."""


class ClaimExtractionError(RuntimeError):
    """Base claim extraction error."""


class ClaimProviderError(ClaimExtractionError):
    """Claim provider request failed."""


class ClaimProviderTimeoutError(ClaimProviderError):
    """Claim provider timed out."""


class ClaimProviderRateLimitError(ClaimProviderError):
    """Claim provider rate limit was reached."""


class ClaimProviderConfigurationError(ClaimProviderError):
    """Claim provider configuration is missing or invalid."""


class ClaimOutputValidationError(ClaimExtractionError):
    """Provider output was malformed or failed schema validation."""


class ClaimGroundingError(ClaimExtractionError):
    """A structured claim could not be grounded in its source evidence."""
