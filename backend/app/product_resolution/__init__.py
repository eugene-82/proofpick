"""Product identity resolution without search or provider side effects."""

from .base import ProductResolver
from .deterministic import DeterministicProductResolver
from .exceptions import ProductInputError, ProductResolutionError
from .models import ProductCandidate, ProductIdentityIssue, ProductResolution
from .search_assisted import (
    ProvisionalProductIdentity,
    SearchAssistedIdentityResolver,
)

__all__ = [
    "DeterministicProductResolver",
    "ProductCandidate",
    "ProductIdentityIssue",
    "ProductInputError",
    "ProductResolution",
    "ProductResolutionError",
    "ProductResolver",
    "ProvisionalProductIdentity",
    "SearchAssistedIdentityResolver",
]
