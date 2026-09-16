"""Adversarial regressions for TASK 011C reliability correctness fixes."""

from collections.abc import Sequence

import pytest
from pydantic import ValidationError

from app.claim_clustering import (
    EmbeddingProvider,
    EvaluationSnapshot,
    SemanticClaimClusterer,
    SnapshotContractError,
)
from app.claim_extraction import (
    ClaimExtractionPayload,
    ClaimExtractionProvider,
    ClaimGroundingError,
    ClaimGroundingValidator,
    ExtractedClaim,
    GroundingAssessment,
    GroundingReasonCode,
    GroundingState,
    StructuredClaimExtractor,
)
from app.confidence import ConfidenceSourceMetadata, EvidenceConfidenceEngine
from app.decision import PurchaseDecisionEngine
from app.evidence_processing import (
    DeterministicEvidenceProcessor,
    EvidenceBudgetPolicy,
    EvidenceCompressor,
    EvidenceQuality,
    ObservationState,
)
from app.models import PurchaseDecision
from app.product_resolution import DeterministicProductResolver
from app.source_filtering import (
    DeterministicSourceFilter,
    IndependenceState,
    SourceCandidate,
    SourceIdentityRegistry,
)
from tests.test_core_reliability_hardening import decision_cluster
from tests.test_reliability_stabilization import candidate, claim, document


class FakeClaimProvider(ClaimExtractionProvider):
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.repairs: list[bool] = []

    def extract_batch(self, documents, *, repair: bool = False):
        self.repairs.append(repair)
        return self.responses.pop(0)


class VectorProvider(EmbeddingProvider):
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.vectors[text] for text in texts]


def _ground(item: ExtractedClaim, text: str):
    return ClaimGroundingValidator().validate(
        ClaimExtractionPayload(claims=[item]), [document(text)]
    )


def test_charger_beside_battery_subject_attack_is_blocked() -> None:
    text = "The charger beside the battery suddenly caught fire."
    item = claim("The battery caught fire.", text, severity=5)
    with pytest.raises(ClaimGroundingError) as error:
        _ground(item, text)
    assert error.value.assessments[0].reason_code is (
        GroundingReasonCode.SUBJECT_PREDICATE_MISMATCH
    )


def test_repair_cannot_promote_subject_attack() -> None:
    text = "The charger beside the battery suddenly caught fire."
    short = claim("The battery caught fire.", "caught fire", severity=5)
    repaired = short.model_copy(update={"evidence_fragment": text})
    provider = FakeClaimProvider(
        [
            {"claims": [short.model_dump(mode="json")]},
            {"claims": [repaired.model_dump(mode="json")]},
        ]
    )
    result = StructuredClaimExtractor(provider).extract([document(text)])
    assert result.claims == []
    assert provider.repairs == [False, True]


def test_unexpectedly_failed_normalization_is_preserved() -> None:
    text = "The battery unexpectedly failed completely."
    item = claim("The battery failed completely.", text, severity=5)
    assert _ground(item, text).claims == [item]


def test_clear_pronoun_antecedent_is_preserved() -> None:
    text = "The battery was warm. It failed completely."
    item = claim("It failed completely.", "It failed completely.", severity=5)
    assert _ground(item, text).claims == [item]


def test_ambiguous_pronoun_is_not_verified() -> None:
    text = "The charger was beside the battery. It failed completely."
    item = claim("It failed completely.", "It failed completely.", severity=5)
    with pytest.raises(ClaimGroundingError):
        _ground(item, text)


def test_normal_positive_and_severe_negative_remain_grounded() -> None:
    positive = claim(
        "The battery works reliably.",
        "The battery works reliably.",
        sentiment="positive",
        severity=1,
    )
    severe = claim(
        "The battery failed completely.",
        "The battery failed completely.",
        severity=5,
    )
    assert _ground(positive, positive.claim).claims == [positive]
    assert _ground(severe, severe.claim).claims == [severe]


def test_usage_metadata_failure_keeps_severe_claim_core() -> None:
    item = claim(
        "The battery failed completely.",
        "The battery failed completely.",
        severity=5,
        months=12,
    )
    payload, assessments = ClaimGroundingValidator().validate_with_assessments(
        ClaimExtractionPayload(claims=[item]),
        [document("I used it for 6 months. The battery failed completely.")],
    )
    assert payload.claims[0].severity == 5
    assert payload.claims[0].usage_period_months is None
    assert assessments[0].metadata_issues == [
        GroundingReasonCode.USAGE_PERIOD_DROPPED
    ]


def test_copy_with_long_footer_does_not_become_independent() -> None:
    body = "I used this vacuum for six months. The battery failed completely."
    inputs = [
        candidate(
            f"https://copy-{index}.example/review",
            body + " " + (f"footer-{index} navigation template " * 40),
        )
        for index in range(4)
    ]
    result = DeterministicSourceFilter().filter(inputs)
    assert len(result.accepted_sources) == 1
    assert result.accepted_sources[0].independence_state is IndependenceState.UNKNOWN
    assert len(result.dropped_sources) == 3


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (
            "I used it daily for six months and the battery failed.",
            "I used it daily for six months and the battery never failed.",
        ),
        (
            "I measured 8 hours of battery runtime.",
            "I measured 1 hour of battery runtime.",
        ),
        (
            "I used it daily for six months and the battery failed.",
            "I used it daily for six months and the charger failed.",
        ),
        (
            "Reviewer: Alice. I used it daily and the battery failed.",
            "Reviewer: Bruce. I used it daily and the battery failed.",
        ),
    ],
)
def test_materially_different_near_duplicates_are_preserved(
    left: str, right: str
) -> None:
    result = DeterministicSourceFilter().filter(
        [
            candidate("https://left.example/review", left),
            candidate("https://right.example/review", right),
        ]
    )
    assert len(result.accepted_sources) == 2
    assert not result.dropped_sources


def test_common_irrelevant_sentence_does_not_collapse_contradiction() -> None:
    common = "The packaging was blue and delivery arrived on Tuesday. "
    result = DeterministicSourceFilter().filter(
        [
            candidate(
                "https://left.example/review",
                common + "After six months the battery failed.",
            ),
            candidate(
                "https://right.example/review",
                common + "After six months the battery never failed.",
            ),
        ]
    )
    assert len(result.accepted_sources) == 2


def _run_enrichment_order(order: tuple[str, ...]):
    registry = SourceIdentityRegistry(analysis_id="order-invariant")
    filterer = DeterministicSourceFilter(registry=registry)
    rich = "I used this vacuum daily for six months and the battery failed completely."
    values = {
        "short": candidate("https://a.example/review", "Short review."),
        "rich": candidate("https://a.example/review", rich),
        "copy": candidate("https://b.example/post", rich),
    }
    for name in order:
        filterer.filter([values[name]])
    retained = registry.retained_sources()
    return [
        (
            source.normalized_url,
            source.raw_content,
            source.independence_state,
            source.independence_group_id,
        )
        for source in retained
    ]


def test_short_rich_and_arrival_order_have_same_final_independence() -> None:
    short_first = _run_enrichment_order(("short", "copy", "rich"))
    rich_first = _run_enrichment_order(("rich", "copy", "short"))
    assert short_first == rich_first
    assert len(short_first) == 1
    assert short_first[0][2] is IndependenceState.UNKNOWN


def test_reconciled_alias_reuses_final_representative_and_group() -> None:
    registry = SourceIdentityRegistry(analysis_id="alias-reconciliation")
    filterer = DeterministicSourceFilter(registry=registry)
    rich = "I used this vacuum daily for six months and the battery failed completely."
    filterer.filter([candidate("https://z.example/review", "Short review.")])
    filterer.filter([candidate("https://a.example/copy", rich)])
    enriched = filterer.filter([candidate("https://z.example/review", rich)])
    repeated = filterer.filter([candidate("https://z.example/review", rich)])

    retained = registry.retained_sources()
    assert len(retained) == 1
    assert retained[0].normalized_url == "https://a.example/copy"
    assert retained[0].independence_group_id == "IG001"
    assert enriched.dropped_sources[0].duplicate_of == retained[0].source_key
    assert repeated.dropped_sources[0].duplicate_of == retained[0].source_key
    assert repeated.dropped_sources[0].independence_group_id == "IG001"
@pytest.mark.parametrize(
    ("phrase", "limit"),
    [
        ("did not fail", 62),
        ("never overheated", 80),
        ("not dangerous", 77),
    ],
)
def test_compression_preserves_complete_negated_predicate(
    phrase: str, limit: int
) -> None:
    text = (
        "First ordinary sentence. "
        + "Middle ordinary sentence. " * 5
        + f"The battery {phrase} during testing."
    )
    output = EvidenceCompressor(
        EvidenceBudgetPolicy(max_chars_per_source=limit)
    ).compress(text)
    assert phrase in output.text.casefold()


def test_compression_refill_never_replaces_selected_critical_evidence() -> None:
    text = (
        "Start context. "
        + "X" * 250
        + ". The battery did not fail. "
        + "Y" * 250
        + ". Ending context."
    )
    output = EvidenceCompressor(
        EvidenceBudgetPolicy(max_chars_per_source=200)
    ).compress(text)
    assert "did not fail" in output.text.casefold()
    assert len(output.text) <= 200


def _confidence_inputs(
    *,
    aspect: str,
    observations: list[ObservationState],
    quality: EvidenceQuality = EvidenceQuality.FULL_CONTENT,
):
    sources = [
        ConfidenceSourceMetadata(
            source_id=f"S{index:03d}",
            domain=f"source-{index - 1}.example",
            independence_group_id=f"IG{index:03d}",
            independence_state=IndependenceState.CONFIRMED,
            evidence_quality=quality,
            observation_state=observation,
            verified_claim_count=1,
            extracted_claim_count=1,
        )
        for index, observation in enumerate(observations, start=1)
    ]
    cluster = decision_cluster(
        1,
        [1] * len(sources),
        sentiment="positive",
        aspect=aspect,
    )
    from app.claim_clustering import ClaimClusteringResult

    clustered = ClaimClusteringResult(clusters=[cluster])
    confidence = EvidenceConfidenceEngine().evaluate(clustered, sources)
    return confidence, clustered


def test_durability_without_observation_horizon_cannot_buy_by_count() -> None:
    confidence, clustered = _confidence_inputs(
        aspect="battery",
        observations=[ObservationState.UNKNOWN] * 8,
    )
    decision = PurchaseDecisionEngine().evaluate(confidence, clustered)
    assert not confidence.quality_gate_passed
    assert decision.decision is PurchaseDecision.EARLY_ADOPTER


def test_first_day_plus_unknown_cannot_bypass_durability_gate() -> None:
    confidence, clustered = _confidence_inputs(
        aspect="durability",
        observations=[ObservationState.FIRST_IMPRESSION] * 7
        + [ObservationState.UNKNOWN],
    )
    decision = PurchaseDecisionEngine().evaluate(confidence, clustered)
    assert not confidence.quality_gate_passed
    assert decision.decision is PurchaseDecision.EARLY_ADOPTER


def test_warranty_duration_is_not_established_observation() -> None:
    filtered = DeterministicSourceFilter().filter(
        [
            candidate(
                "https://warranty.example/review",
                "Warranty is for 12 months. The battery works well.",
            )
        ]
    ).accepted_sources[0]
    evidence = DeterministicEvidenceProcessor().process(filtered)
    assert evidence is not None
    assert evidence.observation_state is ObservationState.UNKNOWN


def test_non_durability_full_evidence_can_still_buy() -> None:
    confidence, clustered = _confidence_inputs(
        aspect="comfort",
        observations=[ObservationState.UNKNOWN] * 8,
    )
    assert confidence.quality_gate_passed
    assert PurchaseDecisionEngine().evaluate(
        confidence, clustered
    ).decision is PurchaseDecision.BUY


def _build_snapshot(*, severity: int = 5, analysis_id: str = "analysis-011c"):
    registry = SourceIdentityRegistry(analysis_id=analysis_id)
    sources = DeterministicSourceFilter(registry=registry).filter(
        [
            SourceCandidate(
                url="https://source.example/review",
                title="Review",
                raw_content=(
                    "I used it for six months. "
                    "The battery failed completely."
                ),
                independence_state=IndependenceState.CONFIRMED,
            )
        ]
    ).accepted_sources
    evidence = DeterministicEvidenceProcessor().process_all(sources)
    item = claim(
        "The battery failed completely.",
        "The battery failed completely.",
        severity=severity,
    )
    _, assessments = ClaimGroundingValidator().validate_with_assessments(
        ClaimExtractionPayload(claims=[item]), evidence
    )
    snapshot = EvaluationSnapshot.create(
        analysis_id=analysis_id,
        product=DeterministicProductResolver().resolve("AirPods Pro 2"),
        registry=registry,
        sources=sources,
        evidence_documents=evidence,
        grounding_assessments=assessments,
    )
    return snapshot, registry


def test_model_validate_rejects_unverified_decision_claim() -> None:
    snapshot, _ = _build_snapshot()
    data = snapshot.model_dump(mode="python")
    data["grounding_assessments"][0]["state"] = GroundingState.UNCERTAIN
    data["grounding_assessments"][0]["reason_code"] = (
        GroundingReasonCode.SPECULATION
    )
    with pytest.raises((ValidationError, SnapshotContractError)):
        EvaluationSnapshot.model_validate(data)


def test_snapshot_is_deeply_immutable_and_copy_revalidates() -> None:
    snapshot, _ = _build_snapshot()
    with pytest.raises((ValidationError, TypeError)):
        snapshot.grounding_assessments[0].claim.severity = 1
    with pytest.raises((ValidationError, TypeError, SnapshotContractError)):
        snapshot.model_copy(
            update={
                "grounding_assessments": [
                    GroundingAssessment(
                        claim=snapshot.verified_claims[0],
                        state=GroundingState.UNCERTAIN,
                        reason_code=GroundingReasonCode.SPECULATION,
                        detail="tampered",
                    )
                ]
            }
        )


def test_severity_changes_snapshot_digest() -> None:
    severe, _ = _build_snapshot(severity=5)
    minor, _ = _build_snapshot(severity=1)
    assert severe.snapshot_id != minor.snapshot_id


def test_registry_identity_or_revision_mismatch_is_rejected() -> None:
    snapshot, _ = _build_snapshot()
    data = snapshot.model_dump(mode="python")
    data["registry_id"] = "registry-0000000000000000"
    with pytest.raises((ValidationError, SnapshotContractError)):
        EvaluationSnapshot.model_validate(data)

    data = snapshot.model_dump(mode="python")
    data["registry_revision"] += 1
    with pytest.raises((ValidationError, SnapshotContractError)):
        EvaluationSnapshot.model_validate(data)


def test_valid_snapshot_still_supports_clustering_confidence_and_decision() -> None:
    snapshot, _ = _build_snapshot()
    vectors = {"battery | The battery failed completely.": [1.0, 0.0]}
    clustered = SemanticClaimClusterer(VectorProvider(vectors)).cluster_snapshot(
        snapshot
    )
    confidence = EvidenceConfidenceEngine().evaluate_snapshot(snapshot, clustered)
    decision = PurchaseDecisionEngine().evaluate(confidence, clustered)
    assert clustered.snapshot_id == snapshot.snapshot_id
    assert decision.unresolved_risks
