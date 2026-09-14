import pytest
from pydantic import ValidationError

from app.product_resolution.models import ProductCandidate, ProductResolution
from app.query_generation import (
    DeterministicQueryGenerator,
    InvalidQueryStageError,
    QueryPurpose,
    QueryStage,
    SearchQuery,
    UnresolvedProductError,
)


def resolved_product(category: str = "robot_vacuum") -> ProductResolution:
    return ProductResolution(
        product_name="Roborock Q Revo",
        brand="Roborock",
        category=category,
        canonical_name="Roborock Q Revo",
        confidence=0.95,
        ambiguous=False,
    )


def test_initial_plan_is_bounded_and_preserves_canonical_name() -> None:
    plan = DeterministicQueryGenerator().generate(resolved_product())

    assert plan.stage is QueryStage.INITIAL
    assert plan.budget == 3
    assert len(plan.queries) == 3
    assert plan.product_canonical_name == "Roborock Q Revo"
    assert all(query.text.startswith("Roborock Q Revo") for query in plan.queries)


def test_stages_expand_without_replacing_earlier_queries() -> None:
    generator = DeterministicQueryGenerator()
    initial = generator.generate(resolved_product(), QueryStage.INITIAL)
    expanded = generator.generate(resolved_product(), QueryStage.EXPANDED)
    maximum = generator.generate(resolved_product(), QueryStage.MAXIMUM)

    assert [query.text for query in initial.queries] == [query.text for query in expanded.queries[:3]]
    assert [query.text for query in expanded.queries] == [query.text for query in maximum.queries[:6]]
    assert len(expanded.queries) == 6
    assert len(maximum.queries) == 10


def test_query_plan_has_no_duplicate_query_texts() -> None:
    plan = DeterministicQueryGenerator().generate(resolved_product(), QueryStage.MAXIMUM)

    normalized = {" ".join(query.text.casefold().split()) for query in plan.queries}
    assert len(normalized) == len(plan.queries)


def test_category_specific_robot_vacuum_query_is_added() -> None:
    plan = DeterministicQueryGenerator().generate(resolved_product(), QueryStage.EXPANDED)

    assert any("센서 맵핑" in query.text for query in plan.queries)
    assert any(query.purpose is QueryPurpose.CATEGORY_ISSUE for query in plan.queries)


def test_category_specific_laptop_query_is_added() -> None:
    plan = DeterministicQueryGenerator().generate(resolved_product("laptop"), QueryStage.EXPANDED)

    assert any("발열 배터리" in query.text for query in plan.queries)


def test_unknown_category_uses_generic_fallback() -> None:
    plan = DeterministicQueryGenerator().generate(resolved_product("unknown"), QueryStage.EXPANDED)

    assert any("실사용 문제" in query.text for query in plan.queries)


@pytest.mark.parametrize(
    "product",
    [
        ProductResolution(
            product_name="AirPods Pro",
            canonical_name="AirPods Pro",
            confidence=0.5,
            ambiguous=True,
            candidates=[
                ProductCandidate(
                    product_name="AirPods Pro 2", canonical_name="AirPods Pro 2", confidence=0.8
                )
            ],
        ),
        ProductResolution(product_name="Unknown product", confidence=0.0, ambiguous=True),
    ],
)
def test_ambiguous_or_unresolved_products_are_rejected(product: ProductResolution) -> None:
    with pytest.raises(UnresolvedProductError):
        DeterministicQueryGenerator().generate(product)


def test_query_model_validates_purpose_stage_and_priority() -> None:
    query = SearchQuery(
        text="Roborock Q Revo 실사용 후기",
        purpose=QueryPurpose.GENERAL_REVIEW,
        stage=QueryStage.INITIAL,
        priority=1,
    )

    assert query.model_dump()["stage"] is QueryStage.INITIAL
    with pytest.raises(ValidationError):
        SearchQuery(text="", purpose="general_review", stage="initial", priority=0)
    with pytest.raises(ValidationError):
        SearchQuery(text="query", purpose="general_review", stage="not-a-stage", priority=1)


def test_invalid_generator_stage_is_rejected() -> None:
    with pytest.raises(InvalidQueryStageError):
        DeterministicQueryGenerator().generate(resolved_product(), "not-a-stage")
