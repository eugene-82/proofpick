"""TASK 011D invariant and metamorphic reliability regressions."""

from itertools import permutations

import pytest

from app.claim_clustering import EvaluationSnapshot, SemanticClaimClusterer
from app.claim_extraction import (
    ClaimExtractionPayload,
    ClaimGroundingError,
    ClaimGroundingValidator,
    ClaimVerificationProvider,
    ClaimVerificationVerdict,
    GroundingReasonCode,
    GroundingState,
)
from app.confidence import (
    ConfidenceInputError,
    ConfidenceSourceMetadata,
    ConfidenceQualityIssue,
    EvidenceConfidenceEngine,
)
from app.decision import DecisionInputError, PurchaseDecisionEngine
from app.evidence_processing import (
    DeterministicEvidenceProcessor,
    EvidenceBudgetPolicy,
    EvidenceQuality,
    ObservationState,
)
from app.models import ClaimSentiment, PurchaseDecision
from app.product_resolution import DeterministicProductResolver
from app.search import SearchResult
from app.source_filtering import (
    DeterministicSourceFilter,
    IndependenceState,
    SourceCandidate,
    SourceIdentityRegistry,
)
from tests.test_reliability_correctness import (
    VectorProvider,
    _build_snapshot,
)
from tests.test_core_reliability_hardening import decision_cluster
from tests.test_reliability_stabilization import claim, document
from app.claim_clustering import ClaimClusteringResult


def _ground(
    source: str,
    claim_text: str,
    verification: GroundingState = GroundingState.VERIFIED,
):
    item = claim(
        claim_text, source, severity=5, verification=verification
    )
    return ClaimGroundingValidator().validate(
        ClaimExtractionPayload(claims=[item]), [document(source)]
    )


@pytest.mark.parametrize(
    "source",
    [
        "The battery was damaged when the charger caught fire.",
        "The battery's charger caught fire.",
    ],
)
def test_clause_local_relation_blocks_subordinate_or_possessive_subject(
    source: str,
) -> None:
    with pytest.raises(ClaimGroundingError) as error:
        _ground(
            source,
            "The battery caught fire.",
            GroundingState.REJECTED,
        )
    assert error.value.assessments[0].reason_code is (
        GroundingReasonCode.SEMANTIC_REJECTED
    )


@pytest.mark.parametrize(
    "source",
    [
        "Unexpectedly the battery failed completely.",
        "Unexpectedly, the battery failed completely.",
        "The durable battery failed completely.",
    ],
)
def test_grounding_is_invariant_to_leading_modifiers(source: str) -> None:
    assert _ground(source, "The battery failed completely.").claims


def test_pronoun_requires_one_local_antecedent() -> None:
    assert _ground(
        "The battery had been unstable. It failed completely.",
        "It failed completely.",
    ).claims
    with pytest.raises(ClaimGroundingError):
        _ground(
            "The charger and battery were warm. It failed completely.",
            "It failed completely.",
            GroundingState.UNCERTAIN,
        )


def test_repair_cannot_relax_clause_relation() -> None:
    source = "The battery was damaged when the charger caught fire."
    short = claim(
        "The battery caught fire.", "caught fire", severity=5,
        verification=GroundingState.REJECTED,
    )
    repaired = claim(
        "The battery caught fire.", source, severity=5,
        verification=GroundingState.REJECTED,
    )
    from tests.test_reliability_correctness import FakeClaimProvider
    from app.claim_extraction import StructuredClaimExtractor

    result = StructuredClaimExtractor(
        FakeClaimProvider(
            [
                {"claims": [short.model_dump(mode="json")]},
                {"claims": [repaired.model_dump(mode="json")]},
            ]
        )
    ).extract([document(source)])
    assert result.claims == []


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (
            "I was hiking in the mountains when the battery failed.",
            "On the airport train, the battery failed.",
        ),
        (
            "Alice used it for 6 months and the battery failed.",
            "Bruce used it for 6 months and the battery failed.",
        ),
        (
            "I used Product X for 6 months and the battery failed.",
            "I used Product Y for 6 months and the screen cracked.",
        ),
        (
            "The package arrived Tuesday. The battery failed.",
            "The package arrived Tuesday. The battery never failed.",
        ),
    ],
)
def test_shared_claim_or_number_does_not_delete_distinct_observation(
    left: str, right: str
) -> None:
    result = DeterministicSourceFilter().filter(
        [
            SourceCandidate(url="https://left.example/r", raw_content=left),
            SourceCandidate(url="https://right.example/r", raw_content=right),
        ]
    )
    assert len(result.accepted_sources) == 2
    assert result.dropped_sources == []


def test_original_body_with_footer_variants_is_one_support_group() -> None:
    body = "I used this vacuum daily for six months. The battery failed completely."
    result = DeterministicSourceFilter().filter(
        [
            SourceCandidate(
                url=f"https://copy-{index}.example/r",
                raw_content=body + (f" footer navigation {index}" * 50),
            )
            for index in range(4)
        ]
    )
    assert len(result.accepted_sources) == 4
    assert result.dropped_sources == []
    assert len(
        {source.independence_group_id for source in result.accepted_sources}
    ) == 1
    assert sum(
        source.independence_state is IndependenceState.CONFIRMED
        for source in result.accepted_sources
    ) <= 1


def test_search_result_has_structural_confirmed_route_without_length_rule() -> None:
    source = SearchResult(
        url="https://review.example/direct",
        title="Owner review",
        raw_content=(
            "I used this vacuum daily for six months. "
            "The battery worked reliably."
        ),
    )
    accepted = DeterministicSourceFilter().filter([source]).accepted_sources[0]
    assert accepted.independence_state is IndependenceState.CONFIRMED

    verbose_but_unattributed = SearchResult(
        url="https://review.example/summary",
        title="Summary",
        raw_content="Marketing description " * 200,
    )
    unknown = DeterministicSourceFilter().filter(
        [verbose_but_unattributed]
    ).accepted_sources[0]
    assert unknown.independence_state is IndependenceState.UNKNOWN


def _ingested_registry(
    order: tuple[str, ...], *, incremental: bool = True
) -> SourceIdentityRegistry:
    registry = SourceIdentityRegistry(analysis_id="arrival-invariant")
    filterer = DeterministicSourceFilter(registry=registry)
    base = "I used this vacuum daily for six months. The battery failed completely."
    items = {
        "copy": SourceCandidate(url="https://z.example/copy", raw_content=base),
        "canonical_short": SourceCandidate(
            url="https://a.example/review", raw_content="Short owner review."
        ),
        "canonical_rich": SourceCandidate(
            url="https://a.example/review",
            raw_content=base + " The casing became dangerously hot later.",
        ),
    }
    if incremental:
        for name in order:
            filterer.filter([items[name]])
    else:
        filterer.filter([items[name] for name in order])
    return registry


def _registry_semantics(
    order: tuple[str, ...], *, incremental: bool = True
):
    registry = _ingested_registry(order, incremental=incremental)
    return tuple(
        (
            source.source_key,
            source.normalized_url,
            source.raw_content,
            source.independence_state,
            source.independence_group_id,
        )
        for source in registry.retained_sources()
    )


def test_registry_final_state_converges_for_all_enrichment_orders() -> None:
    orders = tuple(permutations(("copy", "canonical_short", "canonical_rich")))
    states = [_registry_semantics(order) for order in orders]
    assert all(state == states[0] for state in states)
    assert len(states[0]) == 2
    assert [item[0] for item in states[0]] == ["S001", "S002"]
    assert states[0][0][1] == "https://a.example/review"
    assert "dangerously hot" in (states[0][0][2] or "")
    assert len({item[4] for item in states[0]}) == 1


def test_all_at_once_and_incremental_ingestion_converge() -> None:
    order = ("copy", "canonical_short", "canonical_rich")
    assert _registry_semantics(order) == _registry_semantics(
        order, incremental=False
    )



def test_arrival_permutations_converge_through_decision() -> None:
    outcomes = []
    for order in permutations(("copy", "canonical_short", "canonical_rich")):
        registry = _ingested_registry(order)
        sources = registry.retained_sources()
        documents = DeterministicEvidenceProcessor().process_all(sources)
        product = DeterministicProductResolver().resolve("AirPods Pro 2")
        item = claim(
            "The battery failed completely.",
            "The battery failed completely.",
            source_id=documents[0].source_key,
            sentiment="negative",
            severity=5,
            months=6,
            target_product_id=product.canonical_name,
        )
        _, assessments = ClaimGroundingValidator(
            product
        ).validate_with_assessments(
            ClaimExtractionPayload(claims=[item]), documents
        )
        snapshot = EvaluationSnapshot.create(
            analysis_id=registry.analysis_id,
            product=product,
            registry=registry,
            sources=sources,
            evidence_documents=documents,
            grounding_assessments=assessments,
        )
        clustered = SemanticClaimClusterer(
            VectorProvider(
                {"battery | The battery failed completely.": [1.0, 0.0]}
            )
        ).cluster_snapshot(snapshot)
        confidence = EvidenceConfidenceEngine().evaluate_snapshot(
            snapshot, clustered
        )
        decision = PurchaseDecisionEngine().evaluate_snapshot(
            snapshot, confidence, clustered
        )
        outcomes.append(
            (
                snapshot.snapshot_id,
                clustered.model_dump(mode="json"),
                confidence.model_dump(mode="json"),
                decision.model_dump(mode="json"),
            )
        )
    assert all(outcome == outcomes[0] for outcome in outcomes)

def test_partial_mega_sentence_is_not_grounding_eligible() -> None:
    raw = "The battery did not " + ("remain stable " * 500) + "fail during testing."
    filtered = DeterministicSourceFilter().filter(
        [SourceCandidate(url="https://mega.example/r", raw_content=raw)]
    ).accepted_sources[0]
    evidence = DeterministicEvidenceProcessor(
        EvidenceBudgetPolicy(max_chars_per_source=120)
    ).process(filtered)
    assert evidence is not None
    assert evidence.truncated
    assert not evidence.grounding_eligible
    with pytest.raises(ClaimGroundingError) as error:
        ClaimGroundingValidator().validate(
            ClaimExtractionPayload(
                claims=[claim("The battery failed.", "fail during testing")]
            ),
            [evidence],
        )
    assert error.value.assessments[0].reason_code is (
        GroundingReasonCode.UNSAFE_PARTIAL_EVIDENCE
    )


def test_unsafe_partial_severe_evidence_blocks_positive_only_buy() -> None:
    registry = SourceIdentityRegistry(analysis_id="unsafe-partial-decision")
    filterer = DeterministicSourceFilter(registry=registry)
    positive_contexts = (
        "I tested it every morning at home.",
        "We used it nightly in a workshop.",
        "I owned it through a busy winter.",
        "I used it on two floors each weekend.",
        "We tested it around pets every day.",
        "I owned it in a small apartment.",
        "I used it after work each evening.",
    )
    positive_results = [
        SearchResult(
            url=f"https://positive-{index}.example/review",
            raw_content=f"{context} The battery worked reliably.",
        )
        for index, context in enumerate(positive_contexts)
    ]
    unsafe_result = SearchResult(
        url="https://unsafe.example/review",
        raw_content=(
            "The battery did not "
            + ("remain stable " * 500)
            + "fail during testing."
        ),
    )
    filterer.filter([*positive_results, unsafe_result])
    sources = registry.retained_sources()
    documents = DeterministicEvidenceProcessor(
        EvidenceBudgetPolicy(max_chars_per_source=120)
    ).process_all(sources)
    positive_documents = [
        item for item in documents if item.domain.startswith("positive-")
    ]
    product = DeterministicProductResolver().resolve("AirPods Pro 2")
    claims = [
        claim(
            "The battery worked reliably.",
            "The battery worked reliably.",
            source_id=item.source_key,
            sentiment="positive",
            severity=1,
            target_product_id=product.canonical_name,
        )
        for item in positive_documents
    ]
    _, assessments = ClaimGroundingValidator(
        product
    ).validate_with_assessments(
        ClaimExtractionPayload(claims=claims), documents
    )
    snapshot = EvaluationSnapshot.create(
        analysis_id=registry.analysis_id,
        product=product,
        registry=registry,
        sources=sources,
        evidence_documents=documents,
        grounding_assessments=assessments,
    )
    clustered = SemanticClaimClusterer(
        VectorProvider({"battery | The battery worked reliably.": [1.0, 0.0]})
    ).cluster_snapshot(snapshot)
    confidence = EvidenceConfidenceEngine().evaluate_snapshot(snapshot, clustered)
    decision = PurchaseDecisionEngine().evaluate_snapshot(
        snapshot, confidence, clustered
    )

    assert not confidence.quality_gate_passed
    assert ConfidenceQualityIssue.UNSAFE_PARTIAL_EVIDENCE in confidence.quality_issues
    assert decision.decision is not PurchaseDecision.BUY


def test_unrelated_safe_coverage_limited_document_does_not_veto_buy() -> None:
    registry = SourceIdentityRegistry(analysis_id="safe-coverage-limited")
    filterer = DeterministicSourceFilter(registry=registry)
    positive_contexts = (
        "I tested it every morning at home.",
        "We used it nightly in a workshop.",
        "I owned it through a busy winter.",
        "I used it on two floors each weekend.",
    )
    positive_results = [
        SearchResult(
            url=f"https://safe-{index}.example/review",
            raw_content=f"{context} The controls worked reliably.",
        )
        for index, context in enumerate(positive_contexts)
    ]
    neutral_results = [
        SearchResult(
            url=f"https://neutral-{index}.example/review",
            raw_content=(
                "An owner describes the included documentation and packaging "
                f"in note {index}."
            ),
        )
        for index in range(3)
    ]
    unrelated_long_document = SearchResult(
        url="https://unrelated.example/review",
        raw_content=(
            "Opening notes cover the packaging. "
            "The reviewer describes the included manual. "
            "Several paragraphs discuss desk layout. "
            "A middle section covers the box dimensions. "
            "The closing notes describe recyclable paper inserts."
        ),
    )
    filterer.filter(
        [*positive_results, *neutral_results, unrelated_long_document]
    )
    sources = registry.retained_sources()
    assert len(sources) == 8
    documents = DeterministicEvidenceProcessor(
        EvidenceBudgetPolicy(max_chars_per_source=160)
    ).process_all(sources)
    unrelated = next(
        item for item in documents if item.domain == "unrelated.example"
    )
    assert unrelated.evidence_coverage_limited
    assert all(segment.grounding_eligible for segment in unrelated.segments)

    product = DeterministicProductResolver().resolve("AirPods Pro 2")
    safe_documents = [
        item for item in documents if item.domain.startswith("safe-")
    ]
    claims = [
        claim(
            "The controls worked reliably.",
            "The controls worked reliably.",
            source_id=item.source_key,
            sentiment="positive",
            severity=1,
            target_product_id=product.canonical_name,
            aspect="comfort",
        )
        for item in safe_documents
    ]
    _, assessments = ClaimGroundingValidator(
        product
    ).validate_with_assessments(
        ClaimExtractionPayload(claims=claims), documents
    )
    snapshot = EvaluationSnapshot.create(
        analysis_id=registry.analysis_id,
        product=product,
        registry=registry,
        sources=sources,
        evidence_documents=documents,
        grounding_assessments=assessments,
    )
    clustered = SemanticClaimClusterer(
        VectorProvider({"comfort | The controls worked reliably.": [1.0, 0.0]})
    ).cluster_snapshot(snapshot)
    confidence = EvidenceConfidenceEngine().evaluate_snapshot(snapshot, clustered)
    decision = PurchaseDecisionEngine().evaluate_snapshot(
        snapshot, confidence, clustered
    )

    assert confidence.metrics.independent_source_count == 4
    assert confidence.quality_gate_passed
    assert decision.decision is PurchaseDecision.BUY


def test_first_day_and_warranty_stays_first_impression() -> None:
    source = "I used it today and the warranty lasts for 12 months."
    first_day = claim(
        "I used it today.",
        source,
        observation_type="FIRST_IMPRESSION",
    ).semantic_relation
    warranty = claim(
        "The warranty lasts for 12 months.",
        source,
        months=12,
        observation_type="WARRANTY",
    ).semantic_relation

    assert EvidenceConfidenceEngine._semantic_observation_state(
        [first_day, warranty]
    ) is ObservationState.FIRST_IMPRESSION


def test_unknown_quality_addition_cannot_improve_quality_gate() -> None:
    baseline_sources = [
        ConfidenceSourceMetadata(
            source_id=f"S{index:03d}",
            domain=f"source-{index - 1}.example",
            independence_group_id=f"IG{index:03d}",
            independence_state=IndependenceState.CONFIRMED,
            evidence_quality=EvidenceQuality.FULL_CONTENT,
            observation_state=ObservationState.UNKNOWN,
            verified_claim_count=1,
            extracted_claim_count=1,
        )
        for index in range(1, 8)
    ]
    baseline_cluster = decision_cluster(
        1, [1] * 7, sentiment="positive", aspect="comfort"
    )
    baseline = EvidenceConfidenceEngine().evaluate(
        ClaimClusteringResult(clusters=[baseline_cluster]), baseline_sources
    )
    extra = ConfidenceSourceMetadata(
        source_id="S008",
        domain="source-7.example",
        independence_group_id="IG008",
        independence_state=IndependenceState.CONFIRMED,
        evidence_quality=EvidenceQuality.UNKNOWN,
        observation_state=ObservationState.UNKNOWN,
        verified_claim_count=1,
        extracted_claim_count=1,
    )
    expanded_cluster = decision_cluster(
        1, [1] * 8, sentiment="positive", aspect="comfort"
    )
    expanded = EvidenceConfidenceEngine().evaluate(
        ClaimClusteringResult(clusters=[expanded_cluster]),
        baseline_sources + [extra],
    )
    assert baseline.quality_gate_passed
    assert not expanded.quality_gate_passed


def _invalid_snapshot(snapshot: EvaluationSnapshot) -> EvaluationSnapshot:
    invalid_assessment = snapshot.grounding_assessments[0].model_copy(
        update={"state": GroundingState.REJECTED}
    )
    return EvaluationSnapshot.model_construct(
        **{
            **snapshot.__dict__,
            "grounding_assessments": (invalid_assessment,),
        }
    )


def test_model_construct_invalid_snapshot_is_rejected_at_all_boundaries() -> None:
    snapshot, _ = _build_snapshot()
    invalid = _invalid_snapshot(snapshot)
    provider = VectorProvider(
        {"battery | The battery failed completely.": [1.0, 0.0]}
    )
    clusterer = SemanticClaimClusterer(provider)
    clustered = clusterer.cluster_snapshot(snapshot)
    confidence = EvidenceConfidenceEngine().evaluate_snapshot(snapshot, clustered)

    with pytest.raises(ValueError):
        clusterer.cluster_snapshot(invalid)
    with pytest.raises(ConfidenceInputError):
        EvidenceConfidenceEngine().evaluate_snapshot(invalid, clustered)
    with pytest.raises(DecisionInputError):
        PurchaseDecisionEngine().evaluate_snapshot(
            invalid, confidence, clustered
        )


def test_url_or_evidence_provenance_mutation_fails_boundary_validation() -> None:
    snapshot, _ = _build_snapshot()
    changed_source = snapshot.sources[0].model_copy(
        update={"normalized_url": "https://attacker.example/review"}
    )
    changed_document = snapshot.evidence_documents[0].model_copy(
        update={"text": "Different evidence text."}
    )
    provider = VectorProvider(
        {"battery | The battery failed completely.": [1.0, 0.0]}
    )
    clusterer = SemanticClaimClusterer(provider)
    for update in (
        {"sources": (changed_source,)},
        {"evidence_documents": (changed_document,)},
        {"registry_manifest": "0" * 64},
    ):
        invalid = EvaluationSnapshot.model_construct(
            **{**snapshot.__dict__, **update}
        )
        with pytest.raises(ValueError):
            clusterer.cluster_snapshot(invalid)


def _pipeline(decision_kind: str, count: int, *, copies: bool = False):
    registry = SourceIdentityRegistry(analysis_id=f"pipeline-{decision_kind}-{copies}")
    filterer = DeterministicSourceFilter(registry=registry)
    positive = decision_kind == "positive"
    sentence = (
        "The battery worked reliably."
        if positive
        else "The battery failed completely."
    )
    observation_contexts = (
        "I used this vacuum every morning at home for 6 months.",
        "We tested this vacuum nightly in a workshop for 6 months.",
        "I owned this vacuum through a busy winter for 6 months.",
        "I used this vacuum on two floors each weekend for 6 months.",
        "We tested this vacuum around pets every day for 6 months.",
        "I owned this vacuum in a small apartment for 6 months.",
        "I used this vacuum after work each evening for 6 months.",
    )
    copied_context = "I used this vacuum daily for 6 months."
    results = [
        SearchResult(
            url=f"https://source-{index}.example/review",
            title="Owner review",
            raw_content=(
                (copied_context if copies else observation_contexts[index])
                + " "
                + sentence
            ),
        )
        for index in range(count)
    ]
    filterer.filter(results)
    sources = registry.retained_sources()
    documents = DeterministicEvidenceProcessor().process_all(sources)
    product = DeterministicProductResolver().resolve("AirPods Pro 2")
    items = [
        claim(
            sentence,
            sentence,
            source_id=document.source_key,
            sentiment="positive" if positive else "negative",
            severity=1 if positive else 5,
            months=6,
            target_product_id=product.canonical_name,
        )
        for document in documents
    ]
    _, assessments = ClaimGroundingValidator(product).validate_with_assessments(
        ClaimExtractionPayload(claims=items), documents
    )
    snapshot = EvaluationSnapshot.create(
        analysis_id=registry.analysis_id,
        product=product,
        registry=registry,
        sources=sources,
        evidence_documents=documents,
        grounding_assessments=assessments,
    )
    vectors = {f"battery | {sentence}": [1.0, 0.0]}
    clustered = SemanticClaimClusterer(VectorProvider(vectors)).cluster_snapshot(
        snapshot
    )
    confidence = EvidenceConfidenceEngine().evaluate_snapshot(snapshot, clustered)
    decision = PurchaseDecisionEngine().evaluate_snapshot(
        snapshot, confidence, clustered
    )
    return decision, confidence, clustered


def test_normal_search_path_can_buy_and_independent_severe_can_skip() -> None:
    positive, positive_confidence, _ = _pipeline("positive", 7)
    severe, _, _ = _pipeline("severe", 4)
    assert positive_confidence.quality_gate_passed
    assert positive.decision is PurchaseDecision.BUY
    assert severe.decision is PurchaseDecision.SKIP


def test_copied_severe_reports_do_not_inflate_support() -> None:
    decision, _, clustered = _pipeline("severe", 4, copies=True)
    assert clustered.clusters[0].independent_source_count == 1
    assert decision.decision is not PurchaseDecision.SKIP

class _VerdictProvider(ClaimVerificationProvider):
    def __init__(self, state: GroundingState) -> None:
        self.state = state
        self.repairs: list[bool] = []

    def verify_batch(
        self,
        claims,
        documents,
        *,
        target_product_id: str,
        repair: bool = False,
    ):
        self.repairs.append(repair)
        verdicts = []
        for item in claims:
            relation = item.semantic_relation.model_copy(
                update={"verification_status": self.state}
            )
            verdicts.append(
                ClaimVerificationVerdict(
                    claim=item,
                    relation=relation,
                    verification_status=self.state,
                    detail=f"fake semantic verdict: {self.state.value}",
                )
            )
        return verdicts


@pytest.mark.parametrize(
    ("state", "accepted"),
    [
        (GroundingState.VERIFIED, True),
        (GroundingState.UNCERTAIN, False),
        (GroundingState.REJECTED, False),
    ],
)
def test_semantic_provider_verdict_is_authoritative(
    state: GroundingState, accepted: bool
) -> None:
    source = "Unexpectedly the battery failed completely."
    item = claim("The battery failed completely.", source, severity=5)
    validator = ClaimGroundingValidator(
        verification_provider=_VerdictProvider(state)
    )
    if accepted:
        assert validator.validate(
            ClaimExtractionPayload(claims=[item]), [document(source)]
        ).claims
    else:
        with pytest.raises(ClaimGroundingError):
            validator.validate(
                ClaimExtractionPayload(claims=[item]), [document(source)]
            )


def test_repair_reenters_the_same_semantic_verifier() -> None:
    from app.claim_extraction import StructuredClaimExtractor
    from tests.test_reliability_correctness import FakeClaimProvider

    source = "The battery was damaged when the charger caught fire."
    initial = claim("The battery caught fire.", "caught fire", severity=5)
    repaired = claim("The battery caught fire.", source, severity=5)
    extractor = FakeClaimProvider(
        [
            {"claims": [initial.model_dump(mode="json")]},
            {"claims": [repaired.model_dump(mode="json")]},
        ]
    )
    verifier = _VerdictProvider(GroundingState.REJECTED)
    result = StructuredClaimExtractor(
        extractor,
        grounding_validator=ClaimGroundingValidator(
            verification_provider=verifier
        ),
    ).extract([document(source)])

    assert result.claims == []
    assert verifier.repairs == [False, True]


def _derived_artifacts():
    snapshot, _ = _build_snapshot()
    clustered = SemanticClaimClusterer(
        VectorProvider(
            {"battery | The battery failed completely.": [1.0, 0.0]}
        )
    ).cluster_snapshot(snapshot)
    confidence = EvidenceConfidenceEngine().evaluate_snapshot(
        snapshot, clustered
    )
    return snapshot, clustered, confidence


def test_rehashed_cluster_deletion_and_sentiment_laundering_are_rejected() -> None:
    snapshot, clustered, _ = _derived_artifacts()
    deleted = clustered.model_copy(update={"clusters": []})
    deleted = deleted.model_copy(
        update={"content_digest": deleted.expected_content_digest()}
    )
    with pytest.raises(ConfidenceInputError):
        EvidenceConfidenceEngine().evaluate_snapshot(snapshot, deleted)

    cluster = clustered.clusters[0]
    laundered_cluster = cluster.model_copy(
        update={"sentiment": ClaimSentiment.POSITIVE}
    )
    laundered = clustered.model_copy(update={"clusters": [laundered_cluster]})
    laundered = laundered.model_copy(
        update={"content_digest": laundered.expected_content_digest()}
    )
    with pytest.raises(ConfidenceInputError):
        EvidenceConfidenceEngine().evaluate_snapshot(snapshot, laundered)


def test_rehashed_forged_confidence_is_rejected_by_decision() -> None:
    snapshot, clustered, confidence = _derived_artifacts()
    forged = confidence.model_copy(
        update={
            "overall_score": 1.0,
            "quality_gate_passed": True,
            "quality_issues": [],
        }
    )
    forged = forged.model_copy(
        update={"content_digest": forged.expected_content_digest()}
    )
    with pytest.raises(DecisionInputError):
        PurchaseDecisionEngine().evaluate_snapshot(
            snapshot, forged, clustered
        )


def test_snapshot_bound_artifacts_cannot_use_legacy_entrypoints() -> None:
    _, clustered, confidence = _derived_artifacts()
    with pytest.raises(ConfidenceInputError):
        EvidenceConfidenceEngine().evaluate(clustered, [])
    with pytest.raises(DecisionInputError):
        PurchaseDecisionEngine().evaluate(confidence, clustered)
