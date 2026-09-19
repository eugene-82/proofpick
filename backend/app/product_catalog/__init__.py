"""Submission-safe demo product alias catalog."""

from .catalog import AMBIGUOUS_ALIASES, DEMO_PRODUCT_CATALOG, PRODUCTS
from .catalog import CatalogValidationError, DemoProductCatalog
from .models import CatalogCategory, DemoProduct, ProductLifecycle
from .normalize import normalize_catalog_alias


def canonicalize_demo_product(value: str) -> str:
    """Return a known canonical name, otherwise preserve the exact input."""
    return DEMO_PRODUCT_CATALOG.canonicalize(value)


__all__ = [
    "AMBIGUOUS_ALIASES", "CatalogCategory", "CatalogValidationError",
    "DEMO_PRODUCT_CATALOG", "DemoProduct", "DemoProductCatalog", "PRODUCTS",
    "ProductLifecycle", "canonicalize_demo_product", "normalize_catalog_alias",
]

