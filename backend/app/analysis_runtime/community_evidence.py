"""Bounded Korean community query planning for insufficient initial evidence."""

from dataclasses import dataclass

from app.models import PurchaseDecision
from app.query_generation.policy import DEFAULT_QUERY_BUDGET_POLICY


@dataclass(frozen=True)
class KoreanCommunityPlan:
    queries: tuple[str, ...]

    @property
    def attempted(self) -> bool:
        return bool(self.queries)


class KoreanCommunityQueryGenerator:
    """Expand only an insufficient analysis using explicit community domains."""

    max_queries = 3
    global_query_budget = DEFAULT_QUERY_BUDGET_POLICY.maximum

    def generate(
        self,
        *,
        product_identity: str,
        decision: PurchaseDecision,
        previous_queries: tuple[str, ...],
    ) -> KoreanCommunityPlan:
        if decision is not PurchaseDecision.EARLY_ADOPTER:
            return KoreanCommunityPlan(queries=())

        candidates = (
            (
                f"{product_identity} "
                "(site:dcinside.com OR site:fmkorea.com) 후기 단점"
            ),
            (
                f"{product_identity} "
                "(site:theqoo.net OR site:arca.live) 후기 문제"
            ),
            f"{product_identity} site:ruliweb.com 실사용 장기 사용",
        )
        remaining_budget = max(
            0, self.global_query_budget - len(previous_queries)
        )
        limit = min(self.max_queries, remaining_budget)
        if limit == 0:
            return KoreanCommunityPlan(queries=())

        existing = {self._normalized(query) for query in previous_queries}
        queries: list[str] = []
        for candidate in candidates:
            normalized = self._normalized(candidate)
            if normalized in existing:
                continue
            existing.add(normalized)
            queries.append(candidate)
            if len(queries) == limit:
                break
        return KoreanCommunityPlan(queries=tuple(queries))

    @staticmethod
    def _normalized(query: str) -> str:
        return " ".join(query.casefold().split())
