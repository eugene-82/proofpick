"""Explicit, configurable limits for progressive query planning."""

from dataclasses import dataclass

from .models import QueryStage


@dataclass(frozen=True)
class QueryBudgetPolicy:
    """Maximum query counts allowed at each planning stage."""

    initial: int = 3
    expanded: int = 6
    maximum: int = 10

    def __post_init__(self) -> None:
        if min(self.initial, self.expanded, self.maximum) < 1:
            raise ValueError("query budgets must be positive")
        if not self.initial <= self.expanded <= self.maximum:
            raise ValueError("query budgets must increase by stage")

    def budget_for(self, stage: QueryStage) -> int:
        return {
            QueryStage.INITIAL: self.initial,
            QueryStage.EXPANDED: self.expanded,
            QueryStage.MAXIMUM: self.maximum,
        }[stage]


DEFAULT_QUERY_BUDGET_POLICY = QueryBudgetPolicy()
