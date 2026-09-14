"""Product identity resolution without search or provider side effects."""

from .base import ProductResolver
from .deterministic import DeterministicProductResolver
from .exceptions import ProductInputError, ProductResolutionError
from .models import ProductCandidate, ProductResolution

__all__ = [
    "DeterministicProductResolver",
    "ProductCandidate",
    "ProductInputError",
    "ProductResolution",
    "ProductResolutionError",
    "ProductResolver",
]
