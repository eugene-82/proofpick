"""Adversarial regressions for the midpoint reliability audit."""

from collections.abc import Sequence
from hashlib import sha256

import pytest

from app.claim_clustering import (
    ClaimCluster,
    ClaimClusteringResult,
    ClusterMember,
    EmbeddingProvider,
    SemanticClaimClusterer,
)
from app.claim_extraction import (
    ClaimExtractionPayload,
    ClaimGroundingError,
    ClaimGroundingValidator,
    ExtractedClaim,
    GroundingReasonCode,
    GroundingState,
)
from app.confidence import (
    ConfidenceComponentBreakdown,
    ConfidenceEvidenceMetrics,
    ConfidenceLevel,
    ConfidenceResult,
    EvidenceConfidenceEngine,
)
from app.decision import DecisionReasonCode, PurchaseDecisionEngine
from app.evidence_processing import (
    DeterministicEvidenceProcessor,
    EvidenceBudgetPolicy,
    EvidenceDocument,
    EvidenceSource,
)
from app.models import PurchaseDecision
from app.product_resolution import (
    DeterministicProductResolver,
    ProductIdentityIssue,
)
from app.source_filtering import (
    DeterministicSourceFilter,
    DropReason,
    FilteredSource,
    IndependenceState,
    SourceCandidate,
    SourceIdentityRegistry,
    SourceType,
)


class VectorProvider(EmbeddingProvider):
    def __init__(self, vectors: dict[str, list[float]]) -> None:
        self.vectors = vectors

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [self.vectors[text] for text in texts]


def candidate(
    url: str,
    text: str | None,
    *,
    snippet: str | None = None,
    title: str = "Review",
    independence: IndependenceState = IndependenceState.CONFIRMED,
) -> SourceCandidate:
    return SourceCandidate(
        url=url,
        title=title,
        snippet=snippet,
        raw_content=text,
        independence_state=independence,
    )


def document(text: str, *, source_id: str = "S001") -> EvidenceDocument:
    return EvidenceDocument(
        source_key=source_id,
        original_url="https://example.com/review",
        normalized_url="https://example.com/review",
        domain="example.com",
        title="Review",
        text=text,
        evidence_source=EvidenceSource.RAW_CONTENT,
        original_length=len(text),
        compressed_length=len(text),
        compression_ratio=1,
        truncated=False,
        source_type=SourceType.WEB,
        independence_group_id="IG001",
    )


def claim(
    text: str,
    fragment: str,
    *,
    source_id: str = "S001",
    sentiment: str = "negative",
    severity: int = 3,
    aspect: str = "battery",
    months: int | None = None,
) -> ExtractedClaim:
    return ExtractedClaim(
        source_id=source_id,
        aspect=aspect,
        claim=text,
        sentiment=sentiment,
        severity=severity,
        usage_period_months=months,
        evidence_fragment=fragment,
    )


def confidence(independent_sources: int = 8) -> ConfidenceResult:
    return ConfidenceResult(
        overall_score=0.8,
        confidence_level=ConfidenceLevel.HIGH,
        components=ConfidenceComponentBreakdown(
            evidence_volume_score=0.8,
            independence_score=0.8,
            diversity_score=0.8,
            agreement_score=0.8,
            long_term_score=0,
            commercial_risk_score=0,
        ),
        commercial_risk_penalty=0,
        metrics=ConfidenceEvidenceMetrics(
            cluster_count=1,
            source_count=independent_sources,
            independent_source_count=independent_sources,
            domain_count=independent_sources,
            long_term_source_count=0,
            long_term_independent_source_count=0,
            commercial_signal_group_count=0,
        ),
    )


def decision_cluster(
    cluster_id: int,
    severities: list[int],
    *,
    sentiment: str = "negative",
    aspect: str = "battery",
    group_ids: list[str] | None = None,
    source_start: int = 1,
) -> ClaimCluster:
    groups = group_ids or [f"IG{source_start + index:03d}" for index in range(len(severities))]
    members: list[ClusterMember] = []
    source_ids: list[str] = []
    for index, severity in enumerate(severities):
        source_id = f"S{source_start + index:03d}"
        extracted = claim(
            f"{aspect} evidence {cluster_id}-{index}",
            f"{aspect} evidence {cluster_id}-{index}",
            source_id=source_id,
            sentiment=sentiment,
            severity=severity,
            aspect=aspect,
        )
        members.append(
            ClusterMember(
                claim_id=f"C{cluster_id * 100 + index + 1:03d}",
                claim=extracted,
                embedding_key=sha256(extracted.claim.encode()).hexdigest(),
                independence_group_id=groups[index],
                independence_state=IndependenceState.CONFIRMED,
            )
        )
        source_ids.append(source_id)
    unique_groups = list(dict.fromkeys(groups))
    return ClaimCluster(
        cluster_id=f"CL{cluster_id:03d}",
        canonical_claim=members[0].claim.claim,
        aspect=aspect,
        sentiment=sentiment,
        members=members,
        source_ids=source_ids,
        source_count=len(source_ids),
        independence_group_ids=unique_groups,
        confirmed_independence_group_ids=unique_groups,
        unknown_independence_group_ids=[],
        independent_source_count=len(unique_groups),
        domains=[f"source-{index}.example" for index in range(len(source_ids))],
        domain_count=len(source_ids),
        average_severity=sum(severities) / len(severities),
        max_severity=max(severities),
    )


def decide(*clusters: ClaimCluster):
    return PurchaseDecisionEngine().evaluate(
        confidence(), ClaimClusteringResult(clusters=list(clusters))
    )


def test_cross_domain_copies_do_not_increase_independent_support() -> None:
    text = "I used this product for six months. The battery failed completely."
    result = DeterministicSourceFilter().filter(
        [candidate(f"https://copy-{index}.example/review", text) for index in range(4)]
    )

    assert len(result.accepted_sources) == 1
    assert len(result.dropped_sources) == 3
    assert all(item.independence_state is IndependenceState.DEPENDENT for item in result.dropped_sources)


def test_footer_and_html_wrapper_near_copies_are_dependent() -> None:
    body = "I used this model daily for six months and the battery failed completely."
    result = DeterministicSourceFilter().filter(
        [
            candidate("https://a.example/review", f"<article>{body}</article> Copyright A"),
            candidate("https://b.example/post", f"<main><p>{body}</p></main> Copyright B"),
        ]
    )

    assert len(result.accepted_sources) == 1
    assert result.dropped_sources[0].reason is DropReason.NEAR_DUPLICATE_CONTENT
    assert result.dropped_sources[0].duplicate_of == "S001"


def test_same_domain_distinct_posts_remain_distinct() -> None:
    result = DeterministicSourceFilter().filter(
        [
            candidate("https://forum.example/one", "Battery failed after six months of daily use."),
            candidate("https://forum.example/two", "The hinge cracked, but battery life stayed reliable."),
        ]
    )

    assert len(result.accepted_sources) == 2


def test_unknown_independence_is_not_counted_as_confirmed() -> None:
    filtered = DeterministicSourceFilter().filter(
        [candidate("https://unknown.example/review", "A sufficiently detailed product review.", independence=IndependenceState.UNKNOWN)]
    ).accepted_sources[0]
    extracted = claim("A sufficiently detailed product review", "A sufficiently detailed product review", sentiment="neutral")
    provider = VectorProvider({"battery | A sufficiently detailed product review": [1.0, 0.0]})
    clustering = SemanticClaimClusterer(provider).cluster([extracted], [filtered])
    result = EvidenceConfidenceEngine().evaluate(clustering, [filtered])

    assert clustering.clusters[0].independent_source_count == 0
    assert result.metrics.independent_source_count == 0


def test_same_url_later_richer_result_enriches_stable_representative() -> None:
    filterer = DeterministicSourceFilter()
    first = filterer.filter([candidate("https://example.com/item", None, title="Title only")])
    second = filterer.filter(
        [candidate("https://example.com/item", "After six months the battery failed.")]
    )

    assert second.dropped_sources[0].duplicate_of == "S001"
    assert first.accepted_sources[0].raw_content == "After six months the battery failed."


def test_incremental_filter_runs_keep_ids_unique_and_reconcile_duplicates() -> None:
    registry = SourceIdentityRegistry()
    first_filter = DeterministicSourceFilter(registry=registry)
    second_filter = DeterministicSourceFilter(registry=registry)
    first = first_filter.filter([candidate("https://a.example/one", "First original review text.")])
    second = second_filter.filter(
        [
            candidate("https://b.example/two", "Second distinct review text."),
            candidate("https://copy.example/one", "First original review text."),
        ]
    )

    accepted = first.accepted_sources + second.accepted_sources
    assert [source.source_key for source in accepted] == ["S001", "S002"]
    assert [source.independence_group_id for source in accepted] == ["IG001", "IG002"]
    assert second.dropped_sources[0].source_key == "S003"
    assert second.dropped_sources[0].duplicate_of == "S001"


def test_unsupported_semantic_claim_is_not_verified() -> None:
    payload = ClaimExtractionPayload(
        claims=[claim("The battery catches fire.", "battery", severity=5)]
    )
    with pytest.raises(ClaimGroundingError) as error:
        ClaimGroundingValidator().validate_with_assessments(
            payload, [document("The battery lasts all day.")]
        )

    assessment = error.value.assessments[0]
    assert assessment.state is not GroundingState.VERIFIED
    assert assessment.reason_code in {
        GroundingReasonCode.TINY_FRAGMENT,
        GroundingReasonCode.CLAIM_NOT_SUPPORTED,
    }


def test_negation_reversal_is_rejected() -> None:
    payload = ClaimExtractionPayload(
        claims=[claim("The battery is dangerous.", "battery is not dangerous")]
    )
    with pytest.raises(ClaimGroundingError) as error:
        ClaimGroundingValidator().validate_with_assessments(
            payload, [document("The battery is not dangerous after extended use.")]
        )

    assert error.value.assessments[0].reason_code is GroundingReasonCode.NEGATION_MISMATCH


def test_uncertain_claim_is_excluded_when_valid_claim_exists() -> None:
    valid = claim("The battery failed after six months", "battery failed after six months")
    uncertain = claim("The battery catches fire", "battery lasts all day", severity=5)
    payload, assessments = ClaimGroundingValidator().validate_with_assessments(
        ClaimExtractionPayload(claims=[valid, uncertain]),
        [document("The battery failed after six months. The battery lasts all day.")],
    )

    assert payload.claims == [valid]
    assert assessments[1].state is not GroundingState.VERIFIED


@pytest.mark.parametrize(
    ("source_text", "claim_text", "fragment", "reason"),
    [
        (
            "According to users, the battery failed after six months.",
            "the battery failed after six months",
            "the battery failed after six months",
            GroundingReasonCode.THIRD_PARTY_REPORT,
        ),
        (
            "I have never used this product; the battery failed after six months.",
            "the battery failed after six months",
            "the battery failed after six months",
            GroundingReasonCode.NON_EXPERIENCE,
        ),
        (
            "The battery might fail after six months.",
            "the battery might fail after six months",
            "the battery might fail after six months",
            GroundingReasonCode.SPECULATION,
        ),
        (
            "The battery failed after six months.",
            "The battery failed after six months",
            "battery",
            GroundingReasonCode.TINY_FRAGMENT,
        ),
    ],
)
def test_indirect_speculative_or_tiny_evidence_is_not_verified(
    source_text: str,
    claim_text: str,
    fragment: str,
    reason: GroundingReasonCode,
) -> None:
    with pytest.raises(ClaimGroundingError) as error:
        ClaimGroundingValidator().validate(
            ClaimExtractionPayload(claims=[claim(claim_text, fragment)]),
            [document(source_text)],
        )

    assert error.value.assessments[0].state is not GroundingState.VERIFIED
    assert error.value.assessments[0].reason_code is reason


def test_real_usage_sentence_is_grounded_beside_marketing_copy() -> None:
    source_text = (
        "Official marketing says the battery lasts all day. "
        "I used it for 6 months and the battery failed repeatedly."
    )
    grounded = claim(
        "I used it for 6 months and the battery failed repeatedly",
        "I used it for 6 months and the battery failed repeatedly",
        months=6,
    )

    result = ClaimGroundingValidator().validate(
        ClaimExtractionPayload(claims=[grounded]), [document(source_text)]
    )

    assert result.claims == [grounded]

def test_warranty_and_decimal_are_not_usage_duration() -> None:
    validator = ClaimGroundingValidator()
    for text, fragment in [
        ("Warranty lasts 12 months.", "Warranty lasts 12 months"),
        ("I used it for 0.6 months.", "used it for 0.6 months"),
    ]:
        with pytest.raises(ClaimGroundingError) as error:
            validator.validate(
                ClaimExtractionPayload(
                    claims=[claim(fragment, fragment, sentiment="neutral", months=12 if "Warranty" in text else 6)]
                ),
                [document(text)],
            )
        assert error.value.assessments[0].reason_code is GroundingReasonCode.USAGE_PERIOD_MISMATCH


@pytest.mark.parametrize(
    ("text", "fragment", "months"),
    [
        ("이 제품을 6개월간 사용했고 배터리가 고장났다.", "6개월간 사용했고 배터리가 고장났다", 6),
        ("이 제품을 1년째 사용했고 배터리가 고장났다.", "1년째 사용했고 배터리가 고장났다", 12),
    ],
)
def test_korean_usage_duration_is_grounded(text: str, fragment: str, months: int) -> None:
    payload = ClaimExtractionPayload(
        claims=[claim(fragment, fragment, months=months)]
    )

    assert ClaimGroundingValidator().validate(payload, [document(text)]).claims


def test_previous_generation_evidence_is_rejected() -> None:
    target = DeterministicProductResolver().resolve("AirPods Pro 2")
    payload = ClaimExtractionPayload(
        claims=[claim("AirPods Pro 1 battery failed", "AirPods Pro 1 battery failed")]
    )
    with pytest.raises(ClaimGroundingError) as error:
        ClaimGroundingValidator(target).validate(
            payload, [document("AirPods Pro 1 battery failed after six months.")]
        )

    assert error.value.assessments[0].reason_code is GroundingReasonCode.PRODUCT_IDENTITY_MISMATCH


def test_product_identity_guards_accessory_comparison_tracking_and_suffixes() -> None:
    resolver = DeterministicProductResolver()
    accessory = resolver.resolve("AirPods Pro 2 case")
    comparison = resolver.resolve("AirPods Pro 2 vs AirPods Pro 3")
    tracking_only = resolver.resolve("https://shop.example/socks?utm_campaign=airpods-pro-2")
    maxv = resolver.resolve("Roborock Q Revo MaxV")

    assert accessory.ambiguous and ProductIdentityIssue.ACCESSORY_INPUT in accessory.identity_issues
    assert comparison.ambiguous and ProductIdentityIssue.COMPARISON_INPUT in comparison.identity_issues
    assert tracking_only.ambiguous and tracking_only.canonical_name is None
    assert maxv.canonical_name == "Roborock Q Revo MaxV"
    assert maxv.model == "MaxV"


def test_ambiguous_family_remains_explicit() -> None:
    result = DeterministicProductResolver().resolve("AirPods Pro")

    assert result.ambiguous
    assert ProductIdentityIssue.AMBIGUOUS_FAMILY in result.identity_issues
    assert len(result.candidates) == 3


def test_compression_keeps_failure_paragraphs_and_negation_context() -> None:
    filler = "Ordinary description " + "x" * 300
    raw = "\n\n".join(
        [
            filler,
            "Battery failed after six months of use. " + "a" * 120,
            filler,
            "The unit did not overheat or catch fire during testing. " + "b" * 120,
            filler,
        ]
    )
    source = FilteredSource(
        source_key="S001",
        original_url="https://example.com/review",
        normalized_url="https://example.com/review",
        domain="example.com",
        title="Review",
        raw_content=raw,
        source_type=SourceType.WEB,
        independence_group_id="IG001",
    )
    result = DeterministicEvidenceProcessor(
        EvidenceBudgetPolicy(max_chars_per_source=240)
    ).process(source)

    assert result is not None
    assert "Battery failed" in result.text
    assert "not overheat" in result.text
    assert "overheat" not in result.text.replace("not overheat", "")


def test_cleaned_empty_raw_falls_back_to_snippet() -> None:
    source = FilteredSource(
        source_key="S001",
        original_url="https://example.com/review",
        normalized_url="https://example.com/review",
        domain="example.com",
        title="Review",
        snippet="Useful first-hand battery evidence.",
        raw_content="<script>tracking()</script><style>body{}</style>",
        source_type=SourceType.WEB,
        independence_group_id="IG001",
    )

    result = DeterministicEvidenceProcessor().process(source)

    assert result is not None
    assert result.text == "Useful first-hand battery evidence."
    assert result.evidence_source is EvidenceSource.SNIPPET


def test_complete_link_guard_breaks_similarity_chain_and_aliases_battery_health() -> None:
    claims = [
        claim(f"claim-{index}", f"claim-{index}", source_id=f"S{index + 1:03d}", aspect="battery_health" if index == 1 else "battery")
        for index in range(4)
    ]
    vectors = {
        f"battery | claim-{index}": vector
        for index, vector in enumerate(
            ([1.0, 0.0], [0.866, 0.5], [0.5, 0.866], [0.0, 1.0])
        )
    }
    sources = [
        FilteredSource(
            source_key=f"S{index + 1:03d}",
            original_url=f"https://source-{index}.example/review",
            normalized_url=f"https://source-{index}.example/review",
            domain=f"source-{index}.example",
            title="Review",
            source_type=SourceType.WEB,
            independence_group_id=f"IG{index + 1:03d}",
            independence_state=IndependenceState.CONFIRMED,
        )
        for index in range(4)
    ]

    clusters = SemanticClaimClusterer(VectorProvider(vectors)).cluster(claims, sources).clusters

    assert len(clusters) >= 2
    assert max(cluster.independent_source_count for cluster in clusters) < 4
    assert clusters[0].aspect == "battery"


def test_neutral_only_evidence_cannot_return_buy() -> None:
    result = decide(decision_cluster(1, [1, 1, 1], sentiment="neutral"))

    assert result.decision is PurchaseDecision.EARLY_ADOPTER
    assert DecisionReasonCode.NO_AFFIRMATIVE_SUPPORT in result.reasons


def test_single_severe_risk_blocks_buy_and_preserves_provenance() -> None:
    severe = decision_cluster(1, [5])
    positives = decision_cluster(2, [1] * 8, sentiment="positive", aspect="comfort", source_start=20)

    result = decide(severe, positives)

    assert result.decision is PurchaseDecision.EARLY_ADOPTER
    assert result.unresolved_risks[0].cluster_id == "CL001"
    assert result.unresolved_risks[0].max_severity == 5
    assert result.unresolved_risks[0].high_severity_independent_support == 1


def test_minor_report_does_not_dilute_repeated_high_severity_issue() -> None:
    baseline = decide(decision_cluster(1, [4, 4, 4, 4]))
    diluted = decide(decision_cluster(1, [4, 4, 4, 4, 1]))

    assert baseline.decision is PurchaseDecision.SKIP
    assert diluted.decision is PurchaseDecision.SKIP
    assert diluted.blocking_issues[0].high_severity_independent_support == 4


def test_duplicate_urls_in_one_group_do_not_change_severity_or_decision() -> None:
    baseline = decision_cluster(1, [5, 3, 3, 3], group_ids=["IG001", "IG002", "IG003", "IG004"])
    duplicated = decision_cluster(
        1,
        [5] * 10 + [3, 3, 3],
        group_ids=["IG001"] * 10 + ["IG002", "IG003", "IG004"],
    )

    baseline_result = decide(baseline)
    duplicate_result = decide(duplicated)
    assert baseline_result.decision is PurchaseDecision.BUY_IF
    assert duplicate_result.decision is PurchaseDecision.BUY_IF
    assert baseline_result.conditions[0].severity == duplicate_result.conditions[0].severity
    assert baseline_result.conditions[0].independent_source_count == 4
    assert duplicate_result.conditions[0].independent_source_count == 4
