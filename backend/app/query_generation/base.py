"""Interface for query-plan generators."""

from abc import ABC, abstractmethod

from app.product_resolution.models import ProductResolution

from .models import QueryPlan, QueryStage


class QueryGenerator(ABC):
    """Build a search query plan without performing a search."""

    @abstractmethod
    def generate(
        self,
        product: ProductResolution,
        stage: QueryStage | str = QueryStage.INITIAL,
    ) -> QueryPlan:
        """Return a bounded query plan for a resolved product."""
