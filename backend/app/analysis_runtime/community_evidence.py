"""Bounded Korean community query planning for insufficient initial evidence."""

from dataclasses import dataclass

from app.models import PurchaseDecision
from app.query_generation.policy import DEFAULT_QUERY_BUDGET_POLICY


_QUERY_PRODUCT_ALIASES = {
    "apple airpods pro (2nd generation)": "에어팟 프로 2",
    "logitech mx master 3s": "로지텍 MX Master 3S",
}


@dataclass(frozen=True)
class KoreanCommunityPlan:
    queries: tuple[str, ...]

    @property
    def attempted(self) -> bool:
        return bool(self.queries)


class KoreanCommunityQueryGenerator:
    """Expand only an insufficient analysis using Korean community names."""

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

        query_product_name = _QUERY_PRODUCT_ALIASES.get(
            self._normalized(product_identity), product_identity
        )
        candidates = (
            f"{query_product_name} 디시인사이드 후기 단점",
            f"{query_product_name} 에펨코리아 후기 문제",
            f"{query_product_name} 루리웹 실사용 장기 사용",
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
