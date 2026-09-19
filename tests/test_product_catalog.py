import pytest

from app.analysis_runtime.service import AnalysisRuntimeService
from app.product_catalog import (
    DEMO_PRODUCT_CATALOG,
    CatalogCategory,
    CatalogValidationError,
    DemoProduct,
    DemoProductCatalog,
    ProductLifecycle,
    canonicalize_demo_product,
)


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("에어팟프로3", "Apple AirPods Pro 3"),
        ("갤럭시버즈4프로", "Samsung Galaxy Buds4 Pro"),
        ("MX 마스터 4", "Logitech MX Master 4"),
        ("닌텐도스위치2", "Nintendo Switch 2"),
        ("드리미X50울트라", "Dreame X50 Ultra"),
    ],
)
def test_korean_safe_aliases_canonicalize(alias: str, canonical: str) -> None:
    assert canonicalize_demo_product(alias) == canonical


@pytest.mark.parametrize(
    "alias",
    [
        "Apple AirPods Pro 3",
        "AirPods Pro 3",
        "  AIRPODS   PRO  3  ",
        "Sony WH 1000XM6",
        "ｌｏｇｉｔｅｃｈ　ＭＸ　Ｍａｓｔｅｒ　４",
    ],
)
def test_english_and_safe_presentation_variants_canonicalize(alias: str) -> None:
    expected = {
        "sony": "Sony WH-1000XM6",
        "logitech": "Logitech MX Master 4",
    }
    folded = alias.casefold().strip()
    canonical = canonicalize_demo_product(alias)
    if "sony" in folded:
        assert canonical == expected["sony"]
    elif "ｌｏｇｉｔｅｃｈ" in folded:
        assert canonical == expected["logitech"]
    else:
        assert canonical == "Apple AirPods Pro 3"


def test_unknown_and_ambiguous_aliases_are_preserved_exactly() -> None:
    assert canonicalize_demo_product("Unknown Product ZX-987") == "Unknown Product ZX-987"
    assert canonicalize_demo_product("  custom unknown  ") == "  custom unknown  "
    assert canonicalize_demo_product("AirPods Pro") == "AirPods Pro"
    assert canonicalize_demo_product("MX Master") == "MX Master"
    assert canonicalize_demo_product("닌텐도 스위치") == "닌텐도 스위치"


def test_catalog_shape_is_balanced_and_alias_index_is_submission_sized() -> None:
    assert len(DEMO_PRODUCT_CATALOG.products) == 75
    assert DEMO_PRODUCT_CATALOG.safe_alias_count == 300
    assert set(DEMO_PRODUCT_CATALOG.category_counts.values()) == {15}
    assert set(DEMO_PRODUCT_CATALOG.category_counts) == set(CatalogCategory)


def test_duplicate_normalized_safe_alias_fails_validation() -> None:
    base = {
        "brand": "Example",
        "category": CatalogCategory.AUDIO,
        "subcategory": "headphones",
        "family": "Example",
        "generation": "1",
        "lifecycle": ProductLifecycle.CURRENT,
        "aliases": ("Shared-100",),
    }
    first = DemoProduct(
        canonical_id="example.first.1", canonical_name="Example First 1", **base
    )
    second = DemoProduct(
        canonical_id="example.second.1",
        canonical_name="Example Second 1",
        **{**base, "aliases": ("shared 100",)},
    )
    with pytest.raises(CatalogValidationError, match="duplicate normalized SAFE alias"):
        DemoProductCatalog((first, second))


@pytest.mark.parametrize(
    ("alias", "canonical"),
    [
        ("에어팟프로3", "Apple AirPods Pro 3"),
        ("갤럭시버즈3프로", "Samsung Galaxy Buds3 Pro"),
        ("갤럭시버즈4프로", "Samsung Galaxy Buds4 Pro"),
        ("MX 마스터 3S", "Logitech MX Master 3S"),
        ("MX 마스터 4", "Logitech MX Master 4"),
        ("큐레보 커브", "Roborock Qrevo Curv"),
        ("큐레보 마스터", "Roborock Qrevo Master"),
        ("울트라기어 32GS95UEB", "LG UltraGear 32GS95UE-B"),
        ("울트라기어 27GX790AB", "LG UltraGear 27GX790A-B"),
    ],
)
def test_generation_variant_and_model_tokens_do_not_collide(
    alias: str, canonical: str
) -> None:
    assert canonicalize_demo_product(alias) == canonical


def test_analysis_runtime_uses_canonical_query_before_existing_resolver(monkeypatch) -> None:
    service = object.__new__(AnalysisRuntimeService)

    class CapturedQuery(RuntimeError):
        pass

    def capture(value: str):
        assert value == "Apple AirPods Pro 3"
        raise CapturedQuery

    monkeypatch.setattr(service, "_resolve_product", capture)
    with pytest.raises(CapturedQuery):
        service.analyze("에어팟프로3")

