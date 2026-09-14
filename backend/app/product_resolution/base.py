"""Provider-independent product resolver interface."""

from abc import ABC, abstractmethod

from .models import ProductResolution


class ProductResolver(ABC):
    """Convert one user input into a validated product identity."""

    @abstractmethod
    def resolve(self, product_input: str) -> ProductResolution:
        """Resolve one product name or URL without running search."""
