import pytest

from app.analysis_runtime import KoreanCommunityQueryGenerator
from app.models import PurchaseDecision


def generate(
    decision: PurchaseDecision,
    *,
    product_identity: str = "Example Headphones",
    previous_queries: tuple[str, ...] = (
        "Example Headphones 실사용 후기",
        "Example Headphones 단점 문제",
        "Example Headphones 장기 사용",
    ),
):
    return KoreanCommunityQueryGenerator().generate(
        product_identity=product_identity,
        decision=decision,
        previous_queries=previous_queries,
    )


def test_early_adopter_generates_three_explicit_korean_community_queries() -> None:
    plan = generate(PurchaseDecision.EARLY_ADOPTER)

    assert plan.queries == (
        "Example Headphones 디시인사이드 후기 단점",
        "Example Headphones 에펨코리아 후기 문제",
        "Example Headphones 루리웹 실사용 장기 사용",
    )
    assert all("site:" not in query for query in plan.queries)
    assert all(" OR " not in query for query in plan.queries)
    assert all(query.startswith("Example Headphones") for query in plan.queries)


@pytest.mark.parametrize(
    ("canonical_name", "query_alias"),
    [
        ("Apple AirPods Pro (2nd generation)", "에어팟 프로 2"),
        ("Logitech MX Master 3S", "로지텍 MX Master 3S"),
    ],
)
def test_known_products_use_bounded_korean_query_aliases(
    canonical_name: str, query_alias: str
) -> None:
    plan = generate(
        PurchaseDecision.EARLY_ADOPTER,
        product_identity=canonical_name,
    )

    assert len(plan.queries) == 3
    assert all(query.startswith(f"{query_alias} ") for query in plan.queries)


@pytest.mark.parametrize(
    "canonical_name",
    [
        "Example Unknown Product X1",
        "Apple AirPods Pro (3rd generation)",
    ],
)
def test_unmapped_product_keeps_canonical_query_name(canonical_name: str) -> None:
    plan = generate(
        PurchaseDecision.EARLY_ADOPTER,
        product_identity=canonical_name,
    )

    assert len(plan.queries) == 3
    assert all(query.startswith(f"{canonical_name} ") for query in plan.queries)


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
