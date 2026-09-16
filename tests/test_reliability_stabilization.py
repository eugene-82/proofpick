"""Adversarial regression suite for TASK 011B reliability contracts."""

from collections.abc import Sequence
from math import cos, radians, sin

import pytest

from app.claim_clustering import (
    ClaimClusteringResult,
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
from app.confidence import (
    ConfidenceQualityIssue,
    ConfidenceSourceMetadata,
    EvidenceConfidenceEngine,
)
from app.decision import DecisionInputError, PurchaseDecisionEngine
from app.evidence_processing import (
    DeterministicEvidenceProcessor,
    EvidenceBudgetPolicy,
    EvidenceDocument,
    EvidenceQuality,
    EvidenceSource,
    ObservationState,
)
from app.models import PurchaseDecision
from app.product_resolution import DeterministicProductResolver
from app.search import SearchResult
from app.source_filtering import (
    DeterministicSourceFilter,
    IndependenceReasonCode,
    IndependenceState,
    SourceCandidate,
    SourceIdentityRegistry,
    SourceType,
)
from tests.test_core_reliability_hardening import confidence, decision_cluster


class FakeClaimProvider(ClaimExtractionProvider):
    def __init__(self, responses: list[object]) -> None:
        self.responses = responses
        self.repairs: list[bool] = []

    def extract_batch(self, documents: Sequence[EvidenceDocument], *,
                      repair: bool = False) -> object:
        self.repairs.append(repair)
        return self.responses.pop(0)


class VectorProvider(EmbeddingProvider):
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.vectors[text] for text in texts]


def document(text: str, source_id: str = "S001", group_id: str = "IG001") -> EvidenceDocument:
    return EvidenceDocument(
        source_key=source_id, original_url=f"https://{source_id}.example/review",
        normalized_url=f"https://{source_id}.example/review",
        domain=f"{source_id}.example", text=text, evidence_source=EvidenceSource.RAW_CONTENT,
        original_length=len(text), compressed_length=len(text), compression_ratio=1,
        truncated=False, source_type=SourceType.WEB, independence_group_id=group_id,
        independence_state=IndependenceState.CONFIRMED,
        evidence_quality=EvidenceQuality.FULL_CONTENT,
    )


def claim(text: str, fragment: str, *, source_id: str = "S001",
          sentiment: str = "negative", severity: int = 3,
          aspect: str = "battery", months: int | None = None) -> ExtractedClaim:
    return ExtractedClaim(
        source_id=source_id, aspect=aspect, claim=text, sentiment=sentiment,
        severity=severity, usage_period_months=months, evidence_fragment=fragment,
    )


def candidate(url: str, text: str | None, *, snippet: str | None = None) -> SourceCandidate:
    return SourceCandidate(url=url, title="Review", raw_content=text, snippet=snippet)


@pytest.mark.parametrize(
    ("source_text", "claim_text"),
    [
        ("The charger has failed beside the battery.", "The battery has failed."),
        ("The charger suddenly failed beside the battery.", "The battery suddenly failed."),
    ],
)
def test_subject_attack_with_auxiliary_or_adverb_is_rejected(
    source_text: str, claim_text: str
) -> None:
    item = claim(claim_text, source_text)
    with pytest.raises(ClaimGroundingError) as error:
        ClaimGroundingValidator().validate(
            ClaimExtractionPayload(claims=[item]), [document(source_text)]
        )
    assert error.value.assessments[0].reason_code is (
        GroundingReasonCode.SUBJECT_PREDICATE_MISMATCH
    )

def test_charger_subject_attack_and_repair_bypass_are_rejected() -> None:
    source = "The charger caught fire beside the battery."
    unsupported = claim("The battery caught fire.", "The charger caught fire beside the battery.",
                        severity=5)
    with pytest.raises(ClaimGroundingError) as error:
        ClaimGroundingValidator().validate(
            ClaimExtractionPayload(claims=[unsupported]), [document(source)]
        )
    assert error.value.assessments[0].reason_code is GroundingReasonCode.SUBJECT_PREDICATE_MISMATCH

    short = unsupported.model_copy(update={"evidence_fragment": "caught fire"})
    provider = FakeClaimProvider([
        {"claims": [short.model_dump(mode="json")]},
        {"claims": [unsupported.model_dump(mode="json")]},
    ])
    result = StructuredClaimExtractor(provider).extract([document(source)])
    assert not result.claims
    assert provider.repairs == [False, True]


@pytest.mark.parametrize(
    ("text", "item"),
    [
        ("The battery works reliably every day.", claim(
            "The battery works reliably every day.", "The battery works reliably every day.",
            sentiment="positive", severity=1,
        )),
        ("The battery failed completely.", claim(
            "The battery failed completely.", "The battery failed completely.", severity=5,
        )),
    ],
)
def test_normal_positive_and_severe_negative_grounding_survive(text, item) -> None:
    result = ClaimGroundingValidator().validate(
        ClaimExtractionPayload(claims=[item]), [document(text)]
    )
    assert result.claims == [item]


def test_usage_metadata_failure_does_not_discard_claim_core() -> None:
    item = claim("The battery failed completely.", "The battery failed completely.", months=12)
    payload, assessments = ClaimGroundingValidator().validate_with_assessments(
        ClaimExtractionPayload(claims=[item]),
        [document("I used it for 6 months. The battery failed completely.")],
    )
    assert payload.claims[0].usage_period_months is None
    assert assessments[0].metadata_issues == [GroundingReasonCode.USAGE_PERIOD_DROPPED]


def test_search_result_without_provenance_stays_unknown() -> None:
    result = DeterministicSourceFilter().filter([
        SearchResult(
            url="https://review.example/item", title="Review",
            raw_content="I tested this vacuum daily and its battery remained reliable.",
        )
    ])
    source = result.accepted_sources[0]
    assert source.independence_state is IndependenceState.UNKNOWN
    assert source.independence_reason_codes == [
        IndependenceReasonCode.INSUFFICIENT_CONTENT
    ]


def test_opposite_polarity_and_numeric_near_duplicates_are_preserved() -> None:
    prefix = "I used this vacuum every day for six months and the battery "
    result = DeterministicSourceFilter().filter([
        candidate("https://one.example/review", prefix + "never failed."),
        candidate("https://two.example/review", prefix + "failed."),
        candidate("https://three.example/review",
                  "I used this vacuum every day for seven months and the battery failed."),
    ])
    assert len(result.accepted_sources) == 3
    assert not result.dropped_sources
    assert result.accepted_sources[1].independence_state is IndependenceState.UNKNOWN


def test_registry_enrichment_protects_rich_index_and_alias() -> None:
    registry = SourceIdentityRegistry(analysis_id="analysis-1")
    filterer = DeterministicSourceFilter(registry=registry)
    rich = "I used this vacuum daily for six months and the battery failed completely."
    first = filterer.filter([candidate("https://origin.example/review", rich)])
    filterer.filter([candidate("https://origin.example/review", "Short text.")])
    copied = filterer.filter([
        candidate("https://alias.example/post", rich)
    ])
    reappeared = filterer.filter([
        candidate("https://alias.example/post", "Entirely changed content that must not form a new group.")
    ])
    assert first.accepted_sources[0].raw_content == rich
    assert copied.dropped_sources[0].duplicate_of == "S001"
    assert reappeared.dropped_sources[0].duplicate_of == "S001"
    assert reappeared.dropped_sources[0].independence_group_id == "IG001"


def test_incremental_filters_share_registry_identity_and_monotonic_ids() -> None:
    registry = SourceIdentityRegistry(analysis_id="analysis-1")
    first = DeterministicSourceFilter(registry=registry).filter([
        candidate("https://one.example/a", "A distinct substantive first review body.")
    ])
    second = DeterministicSourceFilter(registry=registry).filter([
        candidate("https://two.example/b", "A different substantive second review body.")
    ])
    assert [first.accepted_sources[0].source_key, second.accepted_sources[0].source_key] == [
        "S001", "S002"
    ]
    assert registry.revision == 2


def test_compression_keeps_long_single_paragraph_tail_and_both_polarities() -> None:
    text = (
        "The battery worked reliably without a problem. "
        + "Ordinary observations were recorded. " * 180
        + "The battery failed completely and caught fire."
    )
    compressor = DeterministicEvidenceProcessor(EvidenceBudgetPolicy(max_chars_per_source=4000))
    source = DeterministicSourceFilter().filter([
        candidate("https://long.example/review", text)
    ]).accepted_sources[0]
    output = compressor.process(source)
    assert output is not None
    assert len(output.text) > 3000
    assert "worked reliably without a problem" in output.text
    assert "failed completely and caught fire" in output.text


def test_unresolved_severe_risk_survives_early_adopter_and_buy_if() -> None:
    severe = decision_cluster(1, [5])
    early = PurchaseDecisionEngine().evaluate(
        confidence(independent_sources=1),
        ClaimClusteringResult(
            clusters=[severe]
        ),
    )
    conditional = decision_cluster(2, [2, 2], aspect="noise", source_start=20)
    buy_if = PurchaseDecisionEngine().evaluate(
        confidence(),
        ClaimClusteringResult(
            clusters=[conditional, severe]
        ),
    )
    assert early.decision is PurchaseDecision.EARLY_ADOPTER and early.unresolved_risks
    assert buy_if.decision is PurchaseDecision.BUY_IF
    assert [risk.cluster_id for risk in buy_if.unresolved_risks] == ["CL001"]


def _confidence_case(*, quality: EvidenceQuality, observation=ObservationState.UNKNOWN, aspect="battery"):
    sources = [
        ConfidenceSourceMetadata(
            source_id=f"S{i:03d}", domain=f"source-{i - 1}.example",
            independence_group_id=f"IG{i:03d}",
            evidence_quality=quality, observation_state=observation,
            verified_claim_count=1, extracted_claim_count=1,
        )
        for i in range(1, 9)
    ]
    cluster = decision_cluster(1, [1] * 8, sentiment="positive", aspect=aspect)
    clustered = ClaimClusteringResult(clusters=[cluster])
    return EvidenceConfidenceEngine().evaluate(clustered, sources), clustered


def test_snippet_only_mass_and_first_impression_durability_are_gated() -> None:
    snippet_confidence, clustered = _confidence_case(quality=EvidenceQuality.SNIPPET_ONLY)
    result = PurchaseDecisionEngine().evaluate(snippet_confidence, clustered)
    assert not snippet_confidence.quality_gate_passed
    assert ConfidenceQualityIssue.SNIPPET_ONLY_COVERAGE in snippet_confidence.quality_issues
    assert result.decision is PurchaseDecision.EARLY_ADOPTER

    first_day, _ = _confidence_case(
        quality=EvidenceQuality.FULL_CONTENT,
        observation=ObservationState.FIRST_IMPRESSION,
    )
    assert ConfidenceQualityIssue.INSUFFICIENT_DURABILITY_OBSERVATION in first_day.quality_issues


def test_full_verified_support_can_pass_quality_gate() -> None:
    result, clustered = _confidence_case(
        quality=EvidenceQuality.FULL_CONTENT,
        observation=ObservationState.ESTABLISHED,
    )
    assert result.quality_gate_passed
    assert PurchaseDecisionEngine().evaluate(result, clustered).decision is PurchaseDecision.BUY


def _snapshot_fixture():
    registry = SourceIdentityRegistry(analysis_id="analysis-1")
    sources = DeterministicSourceFilter(registry=registry).filter([
        candidate("https://source.example/review",
                  "I used it for six months. The battery failed completely.")
    ]).accepted_sources
    documents = DeterministicEvidenceProcessor().process_all(sources)
    item = claim("The battery failed completely.", "The battery failed completely.")
    _, assessments = ClaimGroundingValidator().validate_with_assessments(
        ClaimExtractionPayload(claims=[item]), documents
    )
    snapshot = EvaluationSnapshot.create(
        analysis_id="analysis-1",
        product=DeterministicProductResolver().resolve("AirPods Pro 2"),
        registry=registry, sources=sources, evidence_documents=documents,
        grounding_assessments=assessments,
    )
    return snapshot


def test_snapshot_rejects_unverified_claim_and_mismatched_decision_inputs() -> None:
    snapshot = _snapshot_fixture()
    bad = GroundingAssessment(
        claim=snapshot.verified_claims[0], state=GroundingState.UNCERTAIN,
        reason_code=GroundingReasonCode.SPECULATION, detail="not verified",
    )
    registry = SourceIdentityRegistry(analysis_id="analysis-1")
    for source in snapshot.sources:
        registry.record_source(source.source_key)
    with pytest.raises(SnapshotContractError, match="unverified claim"):
        EvaluationSnapshot.create(
            analysis_id="analysis-1",
            product=DeterministicProductResolver().resolve("AirPods Pro 2"),
            registry=registry, sources=snapshot.sources,
            evidence_documents=snapshot.evidence_documents,
            grounding_assessments=[bad],
        )
    with pytest.raises(SnapshotContractError, match="stable product identity"):
        EvaluationSnapshot.create(
            analysis_id="analysis-1",
            product=DeterministicProductResolver().resolve("AirPods Pro"),
            registry=registry, sources=snapshot.sources,
            evidence_documents=snapshot.evidence_documents,
            grounding_assessments=snapshot.grounding_assessments,
        )

    vector = {"battery | The battery failed completely.": [1.0, 0.0]}
    clustered = SemanticClaimClusterer(VectorProvider(vector)).cluster_snapshot(snapshot)
    metadata = [ConfidenceSourceMetadata.from_filtered_source(snapshot.sources[0])]
    evaluated = EvidenceConfidenceEngine().evaluate_snapshot(snapshot, clustered)
    mismatched = evaluated.model_copy(update={"snapshot_id": "snapshot-0000000000000000"})
    with pytest.raises(DecisionInputError):
        PurchaseDecisionEngine().evaluate(mismatched, clustered)


def test_same_claim_set_different_order_has_same_clusters_and_decision() -> None:
    angles = [0, 5, 10, 15, 45]
    claims = [
        claim(f"Battery observation {i}", f"Battery observation {i}",
              source_id=f"S{i + 1:03d}", sentiment="positive", severity=1)
        for i in range(5)
    ]
    vectors = {
        f"battery | Battery observation {i}": [cos(radians(angle)), sin(radians(angle))]
        for i, angle in enumerate(angles)
    }
    sources = [
        DeterministicSourceFilter().filter([
            SourceCandidate(
                url=f"https://d{i}.example/r", title="Review",
                raw_content=f"Battery observation source text number {i}.",
                independence_state=IndependenceState.CONFIRMED,
            )
        ]).accepted_sources[0].model_copy(
            update={"source_key": f"S{i + 1:03d}", "independence_group_id": f"IG{i + 1:03d}"}
        )
        for i in range(5)
    ]
    first = SemanticClaimClusterer(VectorProvider(vectors)).cluster(claims, sources)
    second = SemanticClaimClusterer(VectorProvider(vectors)).cluster(
        [claims[i] for i in (4, 2, 0, 3, 1)], list(reversed(sources))
    )
    assert first == second
    first_conf = EvidenceConfidenceEngine().evaluate(first, sources)
    second_conf = EvidenceConfidenceEngine().evaluate(second, list(reversed(sources)))
    assert PurchaseDecisionEngine().evaluate(first_conf, first) == (
        PurchaseDecisionEngine().evaluate(second_conf, second)
    )


def test_multiple_generation_scope_rejected_and_safe_bundle_resolves() -> None:
    target = DeterministicProductResolver().resolve("AirPods Pro 2")
    item = claim(
        "AirPods Pro 2 works but AirPods Pro 1 battery failed.",
        "AirPods Pro 2 works but AirPods Pro 1 battery failed.",
    )
    with pytest.raises(ClaimGroundingError):
        ClaimGroundingValidator(target).validate(
            ClaimExtractionPayload(claims=[item]),
            [document("AirPods Pro 2 works but AirPods Pro 1 battery failed.")],
        )
    bundle = DeterministicProductResolver().resolve(
        "AirPods Pro 2 with MagSafe Charging Case"
    )
    assert not bundle.ambiguous
    assert bundle.generation == "2nd generation"

def test_unknown_quality_is_gated_but_first_impression_non_durability_is_not() -> None:
    unknown, _ = _confidence_case(quality=EvidenceQuality.UNKNOWN)
    assert not unknown.quality_gate_passed
    assert ConfidenceQualityIssue.UNKNOWN_SOURCE_QUALITY in unknown.quality_issues

    comfort, _ = _confidence_case(
        quality=EvidenceQuality.FULL_CONTENT,
        observation=ObservationState.FIRST_IMPRESSION,
        aspect="comfort",
    )
    assert comfort.quality_gate_passed


def test_canonical_url_remains_enrichable_after_multiple_incremental_batches() -> None:
    filterer = DeterministicSourceFilter(
        registry=SourceIdentityRegistry(analysis_id="analysis-enrichment")
    )
    first = filterer.filter([
        SourceCandidate(url="https://origin.example/review", title="Title only")
    ])
    filterer.filter([
        candidate("https://origin.example/review", "A short but useful review body.")
    ])
    richer = "I used this product daily for twelve months and the battery remained reliable."
    filterer.filter([candidate("https://origin.example/review", richer)])
    assert first.accepted_sources[0].raw_content == richer
