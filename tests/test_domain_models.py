from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models import (
    AnalysisCreate,
    AnalysisRead,
    AnalysisStatus,
    ClaimCreate,
    ClaimSentiment,
    ProductCreate,
    ProductRead,
    PurchaseDecision,
)


def test_purchase_decision_values() -> None:
    assert {decision.value for decision in PurchaseDecision} == {
        "BUY",
        "BUY_IF",
        "SKIP",
        "EARLY_ADOPTER",
    }


def test_analysis_status_values() -> None:
    assert {status.value for status in AnalysisStatus} == {
        "queued",
        "resolving_product",
        "searching",
        "filtering_sources",
        "extracting_claims",
        "clustering_claims",
        "evaluating",
        "searching_counter_evidence",
        "finding_alternatives",
        "verifying_alternatives",
        "complete",
        "failed",
    }


def test_claim_sentiment_values() -> None:
    assert {sentiment.value for sentiment in ClaimSentiment} == {
        "positive",
        "negative",
        "neutral",
    }


def test_models_serialize_to_json_compatible_values() -> None:
    product_id = uuid4()
    timestamp = datetime.now(timezone.utc)
    product = ProductRead(
        id=product_id,
        brand="Acme",
        name="Example Headphones",
        model=None,
        generation=None,
        category="audio",
        canonical_name="acme example headphones",
        created_at=timestamp,
        updated_at=timestamp,
    )
    analysis = AnalysisRead(
        id=uuid4(),
        product_id=product_id,
        status=AnalysisStatus.COMPLETE,
        decision=PurchaseDecision.BUY_IF,
        confidence=0.825,
        summary="Strong evidence with one usage caveat.",
        pipeline_version="v1",
        created_at=timestamp,
        updated_at=timestamp,
        completed_at=timestamp,
    )

    assert product.model_dump(mode="json")["id"] == str(product_id)
    assert analysis.model_dump(mode="json")["status"] == "complete"
    assert analysis.model_dump(mode="json")["decision"] == "BUY_IF"


@pytest.mark.parametrize("severity", [0, 6])
def test_claim_rejects_invalid_severity(severity: int) -> None:
    with pytest.raises(ValidationError):
        ClaimCreate(
            analysis_id=uuid4(),
            claim_code="C001",
            aspect="battery",
            canonical_claim="Battery capacity declines over time.",
            sentiment=ClaimSentiment.NEGATIVE,
            severity=severity,
            source_count=2,
            independent_source_count=2,
        )


def test_missing_required_product_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductCreate(name="Example")


def test_invalid_analysis_status_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AnalysisCreate(product_id=uuid4(), status="unknown")  # type: ignore[arg-type]


def test_independent_source_count_cannot_exceed_source_count() -> None:
    with pytest.raises(ValidationError):
        ClaimCreate(
            analysis_id=uuid4(),
            claim_code="C001",
            aspect="durability",
            canonical_claim="The hinge loosens with repeated use.",
            sentiment=ClaimSentiment.NEGATIVE,
            severity=3,
            source_count=1,
            independent_source_count=2,
        )
