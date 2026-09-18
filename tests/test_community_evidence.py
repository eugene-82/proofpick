import pytest

from app.analysis_runtime import KoreanCommunityQueryGenerator
from app.models import PurchaseDecision


def generate(
    decision: PurchaseDecision,
    *,
    previous_queries: tuple[str, ...] = (
        "Example Headphones 실사용 후기",
        "Example Headphones 단점 문제",
        "Example Headphones 장기 사용",
    ),
):
    return KoreanCommunityQueryGenerator().generate(
        product_identity="Example Headphones",
        decision=decision,
        previous_queries=previous_queries,
    )


def test_early_adopter_generates_three_explicit_korean_community_queries() -> None:
    plan = generate(PurchaseDecision.EARLY_ADOPTER)

    assert len(plan.queries) == 3
    assert "site:dcinside.com" in plan.queries[0]
    assert "site:fmkorea.com" in plan.queries[0]
    assert "site:theqoo.net" in plan.queries[1]
    assert "site:arca.live" in plan.queries[1]
    assert "site:ruliweb.com" in plan.queries[2]
    assert all(query.startswith("Example Headphones") for query in plan.queries)


@pytest.mark.parametrize(
    "decision",
    [
        PurchaseDecision.BUY,
        PurchaseDecision.BUY_IF,
        PurchaseDecision.SKIP,
    ],
)
def test_sufficient_initial_decision_skips_community_queries(
    decision: PurchaseDecision,
) -> None:
    assert generate(decision).queries == ()


def test_community_plan_respects_remaining_global_query_budget() -> None:
    previous = tuple(f"query {index}" for index in range(9))

    plan = generate(
        PurchaseDecision.EARLY_ADOPTER,
        previous_queries=previous,
    )

    assert len(plan.queries) == 1
    assert len(previous) + len(plan.queries) == 10


def test_community_queries_are_deterministic_and_deduplicated() -> None:
    first = generate(PurchaseDecision.EARLY_ADOPTER)
    second = generate(PurchaseDecision.EARLY_ADOPTER)
    existing = generate(
        PurchaseDecision.EARLY_ADOPTER,
        previous_queries=(
            "Example Headphones 실사용 후기",
            "Example Headphones 단점 문제",
            "Example Headphones 장기 사용",
            first.queries[0],
        ),
    )

    assert first == second
    assert first.queries[0] not in existing.queries
    assert len(existing.queries) == 2
