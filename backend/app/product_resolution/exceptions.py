"""Errors for invalid product resolution input."""


class ProductResolutionError(ValueError):
    """Base error for product resolution failures."""


class ProductInputError(ProductResolutionError):
    """The supplied product text or URL is invalid."""
