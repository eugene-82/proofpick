from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import ValidationError

from app.claim_extraction import (
    ClaimExtractionPolicy,
    ClaimExtractionProvider,
    ClaimGroundingValidator,
    ClaimProviderError,
    ExtractedClaim,
    GroundingReasonCode,
    ExtractionFailureCode,
    StructuredClaimExtractor,
)
from app.evidence_processing import EvidenceDocument, EvidenceSource
from app.models import ClaimSentiment
from app.product_resolution import DeterministicProductResolver
from app.source_filtering import SourceType


class FakeClaimProvider(ClaimExtractionProvider):
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[list[EvidenceDocument], bool]] = []
        self.target_product_ids: list[str] = []

    def extract_batch(
        self,
        documents: Sequence[EvidenceDocument],
        *,
        repair: bool = False,
        target_product_id: str = "unspecified-product",
    ) -> Any:
        self.calls.append((list(documents), repair))
        self.target_product_ids.append(target_product_id)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def evidence(
    source_id: str,
    text: str,
    *,
    evidence_source: EvidenceSource = EvidenceSource.RAW_CONTENT,
) -> EvidenceDocument:
    return EvidenceDocument(
        source_key=source_id,
        original_url=f"https://example.com/{source_id}",
        normalized_url=f"https://example.com/{source_id}",
        domain="example.com",
        title=f"Review {source_id}",
        text=text,
        evidence_source=evidence_source,
        original_length=len(text),
        compressed_length=len(text),
        compression_ratio=1,
        truncated=False,
        source_type=SourceType.WEB,
        independence_group_id=f"IG{source_id[1:]}",
    )


def claim(
    source_id: str,
    fragment: str,
    *,
    aspect: str = "performance",
    sentiment: str = "neutral",
    severity: int = 2,
    usage_period_months: int | None = None,
) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "aspect": aspect,
        "claim": fragment,
        "sentiment": sentiment,
        "severity": severity,
        "usage_period_months": usage_period_months,
        "evidence_fragment": fragment,
        "semantic_relation": {
            "target_product_id": "unspecified-product",
            "subject": aspect,
            "predicate": fragment,
            "polarity": "AFFIRMED",
            "experiencer": "reviewer",
            "experience_type": "DIRECT",
            "observation_type": "USAGE" if usage_period_months else "UNKNOWN",
            "observation_months": usage_period_months,
            "evidence_quote": fragment,
            "evidence_source_id": source_id,
            "verification_status": "VERIFIED",
        },
    }


def test_positive_negative_neutral_claims_and_usage_period() -> None:
    documents = [
        evidence("S001", "청소 성능은 만족스럽다."),
        evidence("S002", "8개월 사용 후 배터리가 빨리 닳는다."),
        evidence("S003", "소음은 보통 수준이다."),
    ]
    provider = FakeClaimProvider(
        [
            {
                "claims": [
                    claim(
                        "S001",
                        "청소 성능은 만족스럽다.",
                        aspect="cleaning_performance",
                        sentiment="positive",
                    ),
                    claim(
                        "S002",
                        "8개월 사용 후 배터리가 빨리 닳는다.",
                        aspect="battery",
                        sentiment="negative",
                        severity=3,
                        usage_period_months=8,
                    ),
                    claim("S003", "소음은 보통 수준이다.", aspect="noise"),
                ]
            }
        ]
    )

    result = StructuredClaimExtractor(provider).extract(documents)

    assert [item.sentiment for item in result.claims] == [
        ClaimSentiment.POSITIVE,
        ClaimSentiment.NEGATIVE,
        ClaimSentiment.NEUTRAL,
    ]
    assert result.claims[1].usage_period_months == 8
    assert result.failures == []


def test_mixed_review_can_return_multiple_claims_for_one_source() -> None:
    document = evidence("S001", "배터리는 오래 간다. 앱 연결은 자주 끊긴다.")
    provider = FakeClaimProvider(
        [
            {
                "claims": [
                    claim("S001", "배터리는 오래 간다.", aspect="battery", sentiment="positive"),
                    claim(
                        "S001",
                        "앱 연결은 자주 끊긴다.",
                        aspect="connectivity",
                        sentiment="negative",
                        severity=3,
                    ),
                ]
            }
        ]
    )

    result = StructuredClaimExtractor(provider).extract([document])

    assert len(result.claims) == 2
    assert {item.aspect for item in result.claims} == {"battery", "connectivity"}


def test_no_useful_claim_is_a_successful_empty_result() -> None:
    provider = FakeClaimProvider([{"claims": []}])
    result = StructuredClaimExtractor(provider).extract([evidence("S001", "배송이 빨랐다.")])

    assert result.claims == []
    assert result.failures == []


@pytest.mark.parametrize("severity", [0, 6])
def test_severity_is_limited_to_one_through_five(severity: int) -> None:
    with pytest.raises(ValidationError):
        ExtractedClaim(**claim("S001", "Evidence.", severity=severity))


def test_invalid_sentiment_and_noncanonical_aspect_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ExtractedClaim(**claim("S001", "Evidence.", sentiment="mixed"))
    with pytest.raises(ValidationError):
        ExtractedClaim(**claim("S001", "Evidence.", aspect="Battery Life"))


def test_malformed_output_is_retried_once_then_accepted() -> None:
    valid = {"claims": [claim("S001", "Battery lasts all day.", sentiment="positive")]}
    provider = FakeClaimProvider([{"claims": [{"bad": "schema"}]}, valid])

    result = StructuredClaimExtractor(provider).extract(
        [evidence("S001", "Battery lasts all day.")]
    )

    assert len(result.claims) == 1
    assert [repair for _, repair in provider.calls] == [False, True]


def test_repeated_malformed_output_is_marked_failed() -> None:
    provider = FakeClaimProvider([{"invalid": []}, {"claims": [{"bad": "schema"}]}])
    result = StructuredClaimExtractor(provider).extract([evidence("S001", "Evidence.")])

    assert result.claims == []
    assert result.failures[0].code is ExtractionFailureCode.MALFORMED_OUTPUT
    assert len(provider.calls) == 2


def test_provider_failure_is_marked_without_accepting_claims() -> None:
    provider = FakeClaimProvider([ClaimProviderError("provider unavailable")])
    result = StructuredClaimExtractor(provider).extract([evidence("S001", "Evidence.")])

    assert result.claims == []
    assert result.failures[0].code is ExtractionFailureCode.PROVIDER_ERROR
    assert result.failures[0].source_ids == ["S001"]


def test_source_id_mismatch_retries_then_marks_grounding_failure() -> None:
    invalid = {"claims": [claim("S999", "Evidence.")]}
    provider = FakeClaimProvider([invalid, invalid])
    result = StructuredClaimExtractor(provider).extract([evidence("S001", "Evidence.")])

    assert result.claims == []
    assert result.failures[0].code is ExtractionFailureCode.GROUNDING_ERROR
    assert [repair for _, repair in provider.calls] == [False, True]


def test_unsupported_evidence_fragment_is_not_accepted() -> None:
    invalid = {"claims": [claim("S001", "A fact absent from the source.")]}
    provider = FakeClaimProvider([invalid, invalid])
    result = StructuredClaimExtractor(provider).extract(
        [evidence("S001", "The source only says battery life is acceptable.")]
    )

    assert result.claims == []
    assert result.failures[0].code is ExtractionFailureCode.GROUNDING_ERROR


def test_whitespace_normalized_fragment_is_grounded() -> None:
    provider = FakeClaimProvider(
        [{"claims": [claim("S001", "battery lasts all day", sentiment="positive")]}]
    )
    result = StructuredClaimExtractor(provider).extract(
        [evidence("S001", "Battery   lasts\nall day.")]
    )

    assert len(result.claims) == 1


def test_guessed_usage_period_is_dropped_without_discarding_claim_core() -> None:
    candidate = claim("S001", "Battery performance declined.", usage_period_months=12)
    candidate["semantic_relation"]["observation_type"] = "UNKNOWN"
    candidate["semantic_relation"]["observation_months"] = None
    output = {"claims": [candidate]}
    provider = FakeClaimProvider([output])
    result = StructuredClaimExtractor(provider).extract(
        [evidence("S001", "Battery performance declined.")]
    )

    assert not result.failures
    assert result.claims[0].usage_period_months is None
    assert result.grounding_assessments[0].metadata_issues == [
        GroundingReasonCode.USAGE_PERIOD_DROPPED
    ]


def test_batch_document_count_is_limited() -> None:
    documents = [evidence(f"S{index:03d}", f"Evidence {index}.") for index in range(1, 6)]
    provider = FakeClaimProvider([{"claims": []}, {"claims": []}, {"claims": []}])
    policy = ClaimExtractionPolicy(max_documents_per_batch=2, max_total_chars_per_batch=1_000)

    result = StructuredClaimExtractor(provider, policy).extract(documents)

    assert result.failures == []
    assert [len(batch) for batch, _ in provider.calls] == [2, 2, 1]


def test_batch_character_budget_is_limited() -> None:
    documents = [
        evidence("S001", "a" * 60),
        evidence("S002", "b" * 60),
        evidence("S003", "c" * 30),
    ]
    provider = FakeClaimProvider([{"claims": []}, {"claims": []}])
    policy = ClaimExtractionPolicy(max_documents_per_batch=5, max_total_chars_per_batch=100)

    StructuredClaimExtractor(provider, policy).extract(documents)

    assert [[item.source_key for item in batch] for batch, _ in provider.calls] == [
        ["S001"],
        ["S002", "S003"],
    ]
    assert all(sum(len(item.text) for item in batch) <= 100 for batch, _ in provider.calls)


def test_source_order_and_per_source_claim_order_are_stable() -> None:
    documents = [
        evidence("S001", "First claim. Second claim."),
        evidence("S002", "Third claim."),
    ]
    provider = FakeClaimProvider(
        [
            {
                "claims": [
                    claim("S002", "Third claim."),
                    claim("S001", "First claim."),
                    claim("S001", "Second claim."),
                ]
            }
        ]
    )

    result = StructuredClaimExtractor(provider).extract(documents)

    assert [item.evidence_fragment for item in result.claims] == [
        "First claim.",
        "Second claim.",
        "Third claim.",
    ]


def test_batch_receives_raw_and_snippet_provenance() -> None:
    provider = FakeClaimProvider([{"claims": []}])
    documents = [
        evidence("S001", "Raw.", evidence_source=EvidenceSource.RAW_CONTENT),
        evidence("S002", "Snippet.", evidence_source=EvidenceSource.SNIPPET),
    ]

    StructuredClaimExtractor(provider).extract(documents)

    assert [item.evidence_source for item in provider.calls[0][0]] == [
        EvidenceSource.RAW_CONTENT,
        EvidenceSource.SNIPPET,
    ]


def test_duplicate_evidence_source_ids_are_rejected_before_provider_call() -> None:
    provider = FakeClaimProvider([])

    with pytest.raises(ValueError):
        StructuredClaimExtractor(provider).extract(
            [evidence("S001", "First."), evidence("S001", "Second.")]
        )
    assert provider.calls == []


def test_resolved_product_identity_reaches_extraction_and_verification() -> None:
    product = DeterministicProductResolver().resolve("AirPods Pro 2")
    candidate = claim(
        "S001", "Battery lasts all day.", sentiment="positive"
    )
    candidate["semantic_relation"]["target_product_id"] = product.canonical_name
    provider = FakeClaimProvider([{"claims": [candidate]}])

    result = StructuredClaimExtractor(
        provider,
        grounding_validator=ClaimGroundingValidator(product),
    ).extract([evidence("S001", "Battery lasts all day.")])

    assert provider.target_product_ids == [product.canonical_name]
    assert (
        result.claims[0].semantic_relation.target_product_id
        == product.canonical_name
    )
