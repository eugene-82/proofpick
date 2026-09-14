"""Deterministic query-plan generation for the MVP."""

from app.product_resolution.models import ProductResolution

from .base import QueryGenerator
from .exceptions import InvalidQueryStageError, UnresolvedProductError
from .models import QueryPlan, QueryPurpose, QueryStage, SearchQuery
from .policy import DEFAULT_QUERY_BUDGET_POLICY, QueryBudgetPolicy


CATEGORY_ISSUES: dict[str, tuple[str, str]] = {
    "robot_vacuum": ("센서 맵핑", "문턱 머리카락"),
    "laptop": ("발열 배터리", "팬 소음 힌지"),
    "wireless_earbuds": ("배터리 연결 끊김", "착용감 노이즈 캔슬링"),
    "keyboard": ("채터링 무선 연결", "스테빌 키캡"),
}
DEFAULT_CATEGORY_ISSUES = ("실사용 문제", "내구성")


class DeterministicQueryGenerator(QueryGenerator):
    """Create predictable, progressive queries from a resolved product."""

    def __init__(self, policy: QueryBudgetPolicy = DEFAULT_QUERY_BUDGET_POLICY) -> None:
        self._policy = policy

    def generate(
        self,
        product: ProductResolution,
        stage: QueryStage | str = QueryStage.INITIAL,
    ) -> QueryPlan:
        """Return a plan only when the product identity is unambiguous."""
        requested_stage = self._coerce_stage(stage)
        canonical_name = self._canonical_name_for(product)
        category_issues = CATEGORY_ISSUES.get(product.category or "", DEFAULT_CATEGORY_ISSUES)

        candidates = [
            (f"{canonical_name} 실사용 후기", QueryPurpose.GENERAL_REVIEW, QueryStage.INITIAL),
            (f"{canonical_name} 단점 문제", QueryPurpose.PROBLEM, QueryStage.INITIAL),
            (f"{canonical_name} 장기 사용", QueryPurpose.LONG_TERM, QueryStage.INITIAL),
            (f"{canonical_name} {category_issues[0]}", QueryPurpose.CATEGORY_ISSUE, QueryStage.EXPANDED),
            (f"{canonical_name} 고장 불량", QueryPurpose.FAILURE, QueryStage.EXPANDED),
            (f"{canonical_name} 후회", QueryPurpose.REGRET, QueryStage.EXPANDED),
            (f"{canonical_name} {category_issues[1]}", QueryPurpose.CATEGORY_ISSUE, QueryStage.MAXIMUM),
            (f"{canonical_name} 사용자 커뮤니티", QueryPurpose.COMMUNITY, QueryStage.MAXIMUM),
            (f"{canonical_name} reddit", QueryPurpose.COMMUNITY, QueryStage.MAXIMUM),
            (f"{canonical_name} AS 수리", QueryPurpose.FAILURE, QueryStage.MAXIMUM),
        ]

        budget = self._policy.budget_for(requested_stage)
        queries: list[SearchQuery] = []
        seen_texts: set[str] = set()
        for text, purpose, introduced_at in candidates:
            if not self._is_available_at(introduced_at, requested_stage):
                continue
            normalized_text = " ".join(text.casefold().split())
            if normalized_text in seen_texts:
                continue
            seen_texts.add(normalized_text)
            queries.append(
                SearchQuery(
                    text=text,
                    purpose=purpose,
                    stage=introduced_at,
                    priority=len(queries) + 1,
                )
            )
            if len(queries) == budget:
                break

        return QueryPlan(
            product_canonical_name=canonical_name,
            stage=requested_stage,
            budget=budget,
            queries=queries,
        )

    @staticmethod
    def _canonical_name_for(product: ProductResolution) -> str:
        if product.ambiguous or not product.canonical_name:
            raise UnresolvedProductError(
                "an unambiguous product with a canonical name is required to generate queries"
            )
        return product.canonical_name

    @staticmethod
    def _coerce_stage(stage: QueryStage | str) -> QueryStage:
        try:
            return QueryStage(stage)
        except (TypeError, ValueError) as error:
            raise InvalidQueryStageError(f"unsupported query stage: {stage!r}") from error

    @staticmethod
    def _is_available_at(introduced_at: QueryStage, requested_stage: QueryStage) -> bool:
        order = {
            QueryStage.INITIAL: 0,
            QueryStage.EXPANDED: 1,
            QueryStage.MAXIMUM: 2,
        }
        return order[introduced_at] <= order[requested_stage]
