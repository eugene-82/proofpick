from hashlib import sha256

import pytest
from pydantic import ValidationError

from app.claim_clustering import ClaimCluster, ClaimClusteringResult, ClusterMember
from app.claim_extraction import ExtractedClaim
from app.confidence import (
    ConfidenceInputError,
    ConfidenceLevel,
    ConfidencePolicy,
    ConfidenceSourceMetadata,
    EvidenceConfidenceEngine,
)
from app.source_filtering import FilteredSource, SourceType


def source(
    index: int,
    *,
    domain: str | None = None,
    group: int | None = None,
    commercial_signal: float | None = None,
) -> ConfidenceSourceMetadata:
    return ConfidenceSourceMetadata(
        source_id=f"S{index:03d}",
        domain=domain or f"platform-{index}.example",
        independence_group_id=f"IG{(group or index):03d}",
        commercial_signal=commercial_signal,
    )


def cluster(
    cluster_index: int,
    sources: list[ConfidenceSourceMetadata],
    *,
    aspect: str = "battery",
    sentiment: str = "negative",
    usage_months: int | None = None,
    severity: int = 3,
    duplicate_first_claim: bool = False,
) -> ClaimCluster:
    members = []
    for member_index, metadata in enumerate(sources, start=1):
        claim = ExtractedClaim(
            source_id=metadata.source_id,
            aspect=aspect,
            claim=f"Claim {cluster_index}-{member_index}",
            sentiment=sentiment,
            severity=severity,
            usage_period_months=usage_months,
            evidence_fragment=f"Evidence {cluster_index}-{member_index}",
        )
        members.append(
            ClusterMember(
                claim_id=f"C{cluster_index * 100 + member_index:03d}",
                claim=claim,
                embedding_key=sha256(claim.claim.encode()).hexdigest(),
            )
        )
    if duplicate_first_claim:
        original = members[0]
        members.append(
            ClusterMember(
                claim_id=f"C{cluster_index * 100 + len(members) + 1:03d}",
                claim=original.claim,
                embedding_key=original.embedding_key,
            )
        )
    source_ids = list(dict.fromkeys(item.source_id for item in sources))
    groups = list(dict.fromkeys(item.independence_group_id for item in sources))
    domains = list(dict.fromkeys(item.domain for item in sources))
    return ClaimCluster(
        cluster_id=f"CL{cluster_index:03d}",
        canonical_claim=members[0].claim.claim,
        aspect=aspect,
        sentiment=sentiment,
        members=members,
        source_ids=source_ids,
        source_count=len(source_ids),
        independence_group_ids=groups,
        independent_source_count=len(groups),
        domains=domains,
        domain_count=len(domains),
        average_severity=severity,
        max_severity=severity,
        usage_period_months=[] if usage_months is None else [usage_months],
    )


def evaluate(
    clusters: list[ClaimCluster],
    sources: list[ConfidenceSourceMetadata],
):
    return EvidenceConfidenceEngine().evaluate(
        ClaimClusteringResult(clusters=clusters), sources
    )


def test_no_evidence_returns_zero_low_confidence() -> None:
    result = evaluate([], [])

    assert result.overall_score == 0
    assert result.confidence_level is ConfidenceLevel.LOW
    assert all(value == 0 for value in result.components.model_dump().values())


def test_single_source_stays_low() -> None:
    sources = [source(1)]
    result = evaluate([cluster(1, sources)], sources)

    assert result.confidence_level is ConfidenceLevel.LOW
    assert result.overall_score < 0.4


def test_same_independence_group_is_not_counted_as_independent() -> None:
    sources = [source(index, group=1) for index in range(1, 6)]
    result = evaluate([cluster(1, sources)], sources)

    assert result.metrics.source_count == 5
    assert result.metrics.independent_source_count == 1
    assert result.confidence_level is ConfidenceLevel.LOW


def test_multiple_independent_sources_raise_independence_score() -> None:
    dependent = [source(index, group=1) for index in range(1, 5)]
    independent = [source(index) for index in range(1, 5)]

    dependent_result = evaluate([cluster(1, dependent)], dependent)
    independent_result = evaluate([cluster(1, independent)], independent)

    assert independent_result.components.independence_score > (
        dependent_result.components.independence_score
    )


def test_independence_score_is_monotonic_for_fixed_source_count() -> None:
    scores = []
    for group_count in range(1, 6):
        sources = [source(index, group=min(index, group_count)) for index in range(1, 6)]
        scores.append(evaluate([cluster(1, sources)], sources).components.independence_score)

    assert scores == sorted(scores)
    assert len(set(scores)) == len(scores)


def test_multiple_domains_raise_diversity_score() -> None:
    one_domain = [source(index, domain="same.example") for index in range(1, 5)]
    many_domains = [source(index) for index in range(1, 5)]

    assert evaluate([cluster(1, many_domains)], many_domains).components.diversity_score > (
        evaluate([cluster(1, one_domain)], one_domain).components.diversity_score
    )


def test_same_domain_is_counted_once() -> None:
    sources = [source(index, domain="same.example") for index in range(1, 5)]
    result = evaluate([cluster(1, sources)], sources)

    assert result.metrics.domain_count == 1


def test_repeated_independent_support_raises_agreement() -> None:
    one = [source(1)]
    five = [source(index) for index in range(1, 6)]

    assert evaluate([cluster(1, five)], five).components.agreement_score > (
        evaluate([cluster(1, one)], one).components.agreement_score
    )


def test_conflicting_sentiments_reduce_agreement() -> None:
    sources = [source(index) for index in range(1, 9)]
    aligned = evaluate([cluster(1, sources)], sources)
    conflicted = evaluate(
        [
            cluster(1, sources[:4], sentiment="positive"),
            cluster(2, sources[4:], sentiment="negative"),
        ],
        sources,
    )

    assert conflicted.components.agreement_score < aligned.components.agreement_score


def test_opposite_sentiments_on_different_aspects_do_not_conflict() -> None:
    sources = [source(index) for index in range(1, 7)]
    result = evaluate(
        [
            cluster(1, sources[:3], aspect="battery", sentiment="positive"),
            cluster(2, sources[3:], aspect="noise", sentiment="negative"),
        ],
        sources,
    )
    baseline = evaluate(
        [
            cluster(1, sources[:3], aspect="battery", sentiment="positive"),
            cluster(2, sources[3:], aspect="noise", sentiment="positive"),
        ],
        sources,
    )

    assert result.components.agreement_score == baseline.components.agreement_score


def test_missing_long_term_evidence_scores_zero() -> None:
    sources = [source(index) for index in range(1, 5)]

    assert evaluate([cluster(1, sources)], sources).components.long_term_score == 0


def test_multiple_long_term_independent_sources_raise_score() -> None:
    sources = [source(index) for index in range(1, 6)]
    one_long = [
        cluster(1, [sources[0]], usage_months=12),
        cluster(2, sources[1:]),
    ]
    all_long = [cluster(1, sources, usage_months=12)]

    one_result = evaluate(one_long, sources)
    all_result = evaluate(all_long, sources)

    assert one_result.components.long_term_score < all_result.components.long_term_score
    assert one_result.components.long_term_score < 1


def test_one_twelve_month_review_cannot_make_long_term_score_one() -> None:
    sources = [source(index) for index in range(1, 11)]
    clusters = [
        cluster(1, [sources[0]], usage_months=12),
        cluster(2, sources[1:]),
    ]

    assert evaluate(clusters, sources).components.long_term_score < 0.5


def test_commercial_signal_creates_bounded_penalty() -> None:
    neutral = [source(index, commercial_signal=0.0) for index in range(1, 6)]
    commercial = [source(index, commercial_signal=0.8) for index in range(1, 6)]

    neutral_result = evaluate([cluster(1, neutral)], neutral)
    commercial_result = evaluate([cluster(1, commercial)], commercial)

    assert commercial_result.components.commercial_risk_score == 0.8
    assert commercial_result.commercial_risk_penalty == 0.08
    assert commercial_result.overall_score < neutral_result.overall_score


def test_unknown_commercial_signal_is_not_fabricated_as_zero_data() -> None:
    sources = [source(index) for index in range(1, 4)]
    result = evaluate([cluster(1, sources)], sources)

    assert result.components.commercial_risk_score == 0
    assert result.metrics.commercial_signal_group_count == 0


def test_dependent_commercial_signals_count_as_one_group() -> None:
    sources = [
        source(1, group=1, commercial_signal=0.2),
        source(2, group=1, commercial_signal=0.9),
    ]
    result = evaluate([cluster(1, sources)], sources)

    assert result.components.commercial_risk_score == 0.9
    assert result.metrics.commercial_signal_group_count == 1


def test_source_volume_has_diminishing_returns() -> None:
    scores = []
    for count in (5, 10, 25, 30):
        sources = [source(index) for index in range(1, count + 1)]
        scores.append(evaluate([cluster(1, sources)], sources).components.evidence_volume_score)

    assert scores[1] - scores[0] > scores[3] - scores[2]


def test_domain_diversity_has_diminishing_returns() -> None:
    scores = []
    for count in (2, 5, 10, 13):
        sources = [source(index) for index in range(1, count + 1)]
        scores.append(evaluate([cluster(1, sources)], sources).components.diversity_score)

    assert scores[1] - scores[0] > scores[3] - scores[2]


def test_all_normalized_scores_remain_in_range() -> None:
    sources = [source(index, commercial_signal=1.0) for index in range(1, 31)]
    result = evaluate([cluster(1, sources, usage_months=24)], sources)

    assert 0 <= result.overall_score <= 1
    assert all(0 <= value <= 1 for value in result.components.model_dump().values())
    assert 0 <= result.commercial_risk_penalty <= 1


def test_low_medium_and_high_levels_are_reachable() -> None:
    low_sources = [source(1)]
    medium_sources = [source(index) for index in range(1, 4)]
    high_sources = [source(index) for index in range(1, 11)]

    assert evaluate([cluster(1, low_sources)], low_sources).confidence_level is ConfidenceLevel.LOW
    assert evaluate([cluster(1, medium_sources)], medium_sources).confidence_level is ConfidenceLevel.MEDIUM
    assert evaluate(
        [cluster(1, high_sources, usage_months=12)], high_sources
    ).confidence_level is ConfidenceLevel.HIGH


def test_result_is_deterministic_and_serializable() -> None:
    sources = [source(index) for index in range(1, 6)]
    engine = EvidenceConfidenceEngine()
    clustering = ClaimClusteringResult(clusters=[cluster(1, sources, usage_months=8)])

    first = engine.evaluate(clustering, sources)
    second = engine.evaluate(clustering, sources)

    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_duplicate_claim_from_same_source_does_not_increase_confidence() -> None:
    sources = [source(index) for index in range(1, 4)]
    normal = evaluate([cluster(1, sources)], sources)
    duplicated = evaluate(
        [cluster(1, sources, duplicate_first_claim=True)], sources
    )

    assert duplicated == normal


def test_high_severity_alone_does_not_raise_confidence() -> None:
    sources = [source(1)]
    low_severity = evaluate([cluster(1, sources, severity=1)], sources)
    high_severity = evaluate([cluster(1, sources, severity=5)], sources)

    assert high_severity == low_severity
    assert high_severity.confidence_level is ConfidenceLevel.LOW


def test_filtered_source_converts_without_inventing_commercial_signal() -> None:
    filtered = FilteredSource(
        source_key="S001",
        original_url="https://example.com/review",
        normalized_url="https://example.com/review",
        domain="example.com",
        source_type=SourceType.WEB,
        independence_group_id="IG001",
    )
    metadata = ConfidenceSourceMetadata.from_filtered_source(filtered)

    assert metadata.source_id == "S001"
    assert metadata.commercial_signal is None


def test_missing_or_duplicate_source_metadata_is_rejected() -> None:
    sources = [source(1)]
    clustering = ClaimClusteringResult(clusters=[cluster(1, sources)])

    with pytest.raises(ConfidenceInputError, match="missing"):
        EvidenceConfidenceEngine().evaluate(clustering, [])
    with pytest.raises(ConfidenceInputError, match="duplicate"):
        EvidenceConfidenceEngine().evaluate(clustering, [sources[0], sources[0]])


def test_policy_rejects_invalid_weights_and_thresholds() -> None:
    with pytest.raises(ValidationError, match="weights must sum"):
        ConfidencePolicy(evidence_volume_weight=0.5)
    with pytest.raises(ValidationError, match="medium_threshold"):
        ConfidencePolicy(medium_threshold=0.8, high_threshold=0.7)
