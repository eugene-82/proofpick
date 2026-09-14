import pytest
from pydantic import ValidationError

from app.product_resolution import (
    DeterministicProductResolver,
    ProductCandidate,
    ProductInputError,
    ProductResolution,
)


def test_resolves_explicit_product_name() -> None:
    resolution = DeterministicProductResolver().resolve("  로보락 Q Revo  ")

    assert resolution.brand == "Roborock"
    assert resolution.product_name == "Q Revo"
    assert resolution.category == "robot_vacuum"
    assert resolution.canonical_name == "Roborock Q Revo"
    assert resolution.ambiguous is False
    assert resolution.confidence == 0.95


def test_ambiguous_product_family_returns_candidates() -> None:
    resolution = DeterministicProductResolver().resolve("AirPods Pro")

    assert resolution.ambiguous is True
    assert resolution.canonical_name == "Apple AirPods Pro"
    assert len(resolution.candidates) == 3
    assert {candidate.generation for candidate in resolution.candidates} == {
        "1st generation",
        "2nd generation",
        "3rd generation",
    }


def test_explicit_generation_is_not_ambiguous() -> None:
    resolution = DeterministicProductResolver().resolve("Apple AirPods Pro 3")

    assert resolution.ambiguous is False
    assert resolution.generation == "3rd generation"
    assert resolution.candidates == []


def test_valid_url_is_parsed_without_network_access() -> None:
    resolution = DeterministicProductResolver().resolve(
        "https://www.apple.com/airpods-pro-3/"
    )

    assert resolution.canonical_name == "Apple AirPods Pro (3rd generation)"
    assert resolution.ambiguous is False


@pytest.mark.parametrize("product_input", ["https://", "https://not valid"])
def test_invalid_url_like_input_is_rejected(product_input: str) -> None:
    with pytest.raises(ProductInputError):
        DeterministicProductResolver().resolve(product_input)


@pytest.mark.parametrize("product_input", ["", "   "])
def test_empty_product_input_is_rejected(product_input: str) -> None:
    with pytest.raises(ProductInputError):
        DeterministicProductResolver().resolve(product_input)


def test_unresolved_input_does_not_invent_a_product() -> None:
    resolution = DeterministicProductResolver().resolve("mysterious gadget 42")

    assert resolution.ambiguous is True
    assert resolution.confidence == 0
    assert resolution.canonical_name is None
    assert resolution.candidates == []


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_resolution_confidence_must_be_a_unit_interval(confidence: float) -> None:
    with pytest.raises(ValidationError):
        ProductResolution(ambiguous=True, confidence=confidence)


def test_structured_resolution_validates_candidate_consistency() -> None:
    candidate = ProductCandidate(
        brand="Apple",
        product_name="AirPods Pro",
        canonical_name="Apple AirPods Pro (3rd generation)",
        confidence=0.9,
    )
    resolution = ProductResolution.model_validate(
        {
            "brand": "Apple",
            "product_name": "AirPods Pro",
            "canonical_name": "Apple AirPods Pro",
            "ambiguous": True,
            "confidence": 0.72,
            "candidates": [candidate.model_dump()],
        }
    )

    assert resolution.candidates == [candidate]

    with pytest.raises(ValidationError):
        ProductResolution.model_validate(
            {
                "product_name": "AirPods Pro",
                "canonical_name": "Apple AirPods Pro",
                "ambiguous": False,
                "confidence": 0.9,
                "candidates": [candidate.model_dump()],
            }
        )
