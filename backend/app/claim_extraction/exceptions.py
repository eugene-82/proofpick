"""Claim extraction errors."""

from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import GroundingAssessment


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

    def __init__(
        self,
        message: str,
        assessments: Sequence["GroundingAssessment"] = (),
    ) -> None:
        super().__init__(message)
        self.assessments = tuple(assessments)
