from hashlib import sha256

import pytest
from pydantic import ValidationError

from app.claim_clustering import ClaimCluster, ClaimClusteringResult, ClusterMember
from app.claim_extraction import ExtractedClaim
from app.confidence import (
    ConfidenceComponentBreakdown,
    ConfidenceEvidenceMetrics,
    ConfidenceLevel,
    ConfidenceResult,
)
from app.decision import (
    DecisionPolicy,
    DecisionReasonCode,
    PurchaseDecisionEngine,
    PurchaseDecisionResult,
)
from app.models import PurchaseDecision


def confidence(
    score: float = 0.8,
    *,
    independent_sources: int = 6,
    level: ConfidenceLevel | None = None,
) -> ConfidenceResult:
    if level is None:
        level = (
            ConfidenceLevel.HIGH
            if score >= 0.7
            else ConfidenceLevel.MEDIUM
            if score >= 0.4
            else ConfidenceLevel.LOW
        )
    return ConfidenceResult(
        overall_score=score,
        confidence_level=level,
        components=ConfidenceComponentBreakdown(
            evidence_volume_score=score,
            independence_score=score,
            diversity_score=score,
            agreement_score=score,
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


def cluster(
    cluster_index: int,
    support: int,
    *,
    sentiment: str = "neutral",
    severity: int = 1,
    aspect: str = "build_quality",
    usage_months: int | None = None,
    source_start: int = 1,
    duplicate_members: int = 0,
) -> ClaimCluster:
    members = []
    source_ids = []
    group_ids = []
    domains = []
    for offset in range(support):
        source_number = source_start + offset
        source_id = f"S{source_number:03d}"
        claim = ExtractedClaim(
            source_id=source_id,
            aspect=aspect,
            claim=f"{aspect} claim {cluster_index}-{offset}",
            sentiment=sentiment,
            severity=severity,
            usage_period_months=usage_months,
            evidence_fragment=f"Evidence {cluster_index}-{offset}",
        )
        members.append(
            ClusterMember(
                claim_id=f"C{cluster_index * 100 + offset + 1:03d}",
                claim=claim,
                embedding_key=sha256(claim.claim.encode()).hexdigest(),
            )
        )
        source_ids.append(source_id)
        group_ids.append(f"IG{source_number:03d}")
        domains.append(f"platform-{source_number}.example")
    for duplicate_index in range(duplicate_members):
        original = members[0]
        members.append(
            ClusterMember(
                claim_id=f"C{cluster_index * 100 + support + duplicate_index + 1:03d}",
                claim=original.claim,
                embedding_key=original.embedding_key,
            )
        )
    return ClaimCluster(
        cluster_id=f"CL{cluster_index:03d}",
        canonical_claim=members[0].claim.claim,
        aspect=aspect,
        sentiment=sentiment,
        members=members,
        source_ids=source_ids,
        source_count=support,
        independence_group_ids=group_ids,
        independent_source_count=support,
        domains=domains,
        domain_count=support,
        average_severity=severity,
        max_severity=severity,
        usage_period_months=[] if usage_months is None else [usage_months],
    )


def decide(
    clusters: list[ClaimCluster],
    evidence_confidence: ConfidenceResult | None = None,
) -> PurchaseDecisionResult:
    return PurchaseDecisionEngine().evaluate(
        evidence_confidence or confidence(),
        ClaimClusteringResult(clusters=clusters),
    )


def test_no_evidence_returns_early_adopter() -> None:
    result = decide([], confidence(independent_sources=6))

    assert result.decision is PurchaseDecision.EARLY_ADOPTER
    assert DecisionReasonCode.NO_MEANINGFUL_CLAIMS in result.reasons
    assert not result.evidence_sufficient


def test_low_confidence_returns_early_adopter_even_with_positive_claims() -> None:
    result = decide(
        [cluster(1, 6, sentiment="positive")],
        confidence(0.399999, independent_sources=6),
    )

    assert result.decision is PurchaseDecision.EARLY_ADOPTER
    assert DecisionReasonCode.LOW_EVIDENCE_CONFIDENCE in result.reasons


def test_single_independent_source_returns_early_adopter() -> None:
    result = decide(
        [cluster(1, 1, sentiment="positive")],
        confidence(0.8, independent_sources=1),
    )

    assert result.decision is PurchaseDecision.EARLY_ADOPTER
    assert DecisionReasonCode.INSUFFICIENT_INDEPENDENT_EVIDENCE in result.reasons


def test_sufficient_evidence_without_blocking_issue_returns_buy() -> None:
    result = decide([cluster(1, 6, sentiment="positive")])

    assert result.decision is PurchaseDecision.BUY
    assert result.evidence_sufficient
    assert result.blocking_issues == []
    assert DecisionReasonCode.NO_BLOCKING_ISSUES in result.reasons


def test_mild_repeated_negative_issue_returns_buy_if() -> None:
    result = decide([cluster(1, 2, sentiment="negative", severity=2)])

    assert result.decision is PurchaseDecision.BUY_IF


def test_buy_if_always_contains_a_condition() -> None:
    result = decide([cluster(1, 3, sentiment="negative", severity=3)])

    assert result.conditions
    assert all(condition.sentiment.value == "negative" for condition in result.conditions)


def test_high_severity_repeated_issue_returns_skip() -> None:
    result = decide([cluster(1, 4, sentiment="negative", severity=4)])

    assert result.decision is PurchaseDecision.SKIP
    assert result.blocking_issues


def test_single_severity_five_claim_does_not_return_skip() -> None:
    clusters = [
        cluster(1, 1, sentiment="negative", severity=5),
        cluster(2, 5, sentiment="neutral", source_start=10),
    ]

    assert decide(clusters).decision is not PurchaseDecision.SKIP


def test_one_severe_member_does_not_make_a_repeated_cluster_skip() -> None:
    mixed = cluster(1, 4, sentiment="negative", severity=1)
    members = list(mixed.members)
    severe_claim = members[0].claim.model_copy(update={"severity": 5})
    members[0] = members[0].model_copy(update={"claim": severe_claim})
    mixed = mixed.model_copy(
        update={
            "members": members,
            "average_severity": 2.0,
            "max_severity": 5,
        }
    )

    result = decide([mixed])

    assert result.decision is PurchaseDecision.BUY_IF
    assert result.conditions[0].severity == 2.0
    assert result.conditions[0].max_severity == 5


def test_repeated_severity_four_independent_issue_returns_skip() -> None:
    result = decide([cluster(1, 5, sentiment="negative", severity=4)])

    assert result.decision is PurchaseDecision.SKIP
    assert result.blocking_issues[0].independent_source_count == 5


def test_high_confidence_does_not_automatically_mean_buy() -> None:
    result = decide(
        [cluster(1, 5, sentiment="negative", severity=5)],
        confidence(0.9, independent_sources=8),
    )

    assert result.confidence_score == 0.9
    assert result.decision is PurchaseDecision.SKIP


def test_many_positive_claims_do_not_override_serious_negative_issue() -> None:
    clusters = [
        cluster(1, 20, sentiment="positive", source_start=20),
        cluster(2, 4, sentiment="negative", severity=4, source_start=1),
    ]
    result = decide(clusters, confidence(0.95, independent_sources=24))

    assert result.decision is PurchaseDecision.SKIP
    assert result.supporting_signals
    assert result.blocking_issues[0].cluster_id == "CL002"


def test_strong_conflicting_evidence_is_exposed_on_buy_if() -> None:
    clusters = [
        cluster(1, 4, sentiment="positive", aspect="battery", source_start=1),
        cluster(
            2,
            3,
            sentiment="negative",
            severity=3,
            aspect="battery",
            source_start=10,
        ),
    ]
    result = decide(clusters)

    assert result.decision is PurchaseDecision.BUY_IF
    assert DecisionReasonCode.CONFLICTING_EVIDENCE in result.reasons


def test_weak_conflict_does_not_force_buy_if() -> None:
    clusters = [
        cluster(1, 1, sentiment="positive", aspect="battery", source_start=1),
        cluster(2, 1, sentiment="negative", aspect="battery", source_start=2),
        cluster(3, 4, sentiment="neutral", aspect="design", source_start=10),
    ]

    assert decide(clusters).decision is PurchaseDecision.BUY


def test_duplicate_claims_from_one_source_do_not_inflate_decision_support() -> None:
    baseline = [
        cluster(1, 1, sentiment="negative", severity=4),
        cluster(2, 5, sentiment="neutral", source_start=10),
    ]
    duplicated = [
        cluster(1, 1, sentiment="negative", severity=4, duplicate_members=5),
        cluster(2, 5, sentiment="neutral", source_start=10),
    ]

    assert decide(duplicated) == decide(baseline)


def test_independent_support_changes_buy_to_buy_if() -> None:
    one_source = [
        cluster(1, 1, sentiment="negative", severity=3),
        cluster(2, 5, sentiment="neutral", source_start=10),
    ]
    two_sources = [
        cluster(1, 2, sentiment="negative", severity=3),
        cluster(2, 4, sentiment="neutral", source_start=10),
    ]

    assert decide(one_source).decision is PurchaseDecision.BUY
    assert decide(two_sources).decision is PurchaseDecision.BUY_IF


def test_long_term_negative_issue_is_a_structured_condition() -> None:
    result = decide(
        [cluster(1, 2, sentiment="negative", severity=2, usage_months=6)]
    )

    assert result.decision is PurchaseDecision.BUY_IF
    assert result.conditions[0].reason_code is DecisionReasonCode.LONG_TERM_NEGATIVE_ISSUE
    assert result.conditions[0].long_term_evidence


def test_positive_long_term_evidence_does_not_override_low_confidence() -> None:
    result = decide(
        [cluster(1, 6, sentiment="positive", usage_months=12)],
        confidence(0.3, independent_sources=6),
    )

    assert result.decision is PurchaseDecision.EARLY_ADOPTER


def test_repeated_runs_are_deterministic_and_serializable() -> None:
    clusters = [cluster(1, 3, sentiment="negative", severity=3)]
    engine = PurchaseDecisionEngine()
    clustering = ClaimClusteringResult(clusters=clusters)
    evidence_confidence = confidence()

    first = engine.evaluate(evidence_confidence, clustering)
    second = engine.evaluate(evidence_confidence, clustering)

    assert first == second
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_decision_reasons_use_stable_reason_codes() -> None:
    result = decide([cluster(1, 4, sentiment="negative", severity=4)])

    assert result.reasons == [DecisionReasonCode.REPEATED_HIGH_SEVERITY_ISSUE]
    assert all(isinstance(reason, DecisionReasonCode) for reason in result.reasons)


def test_issue_provenance_is_preserved() -> None:
    result = decide(
        [
            cluster(
                7,
                4,
                sentiment="negative",
                severity=4,
                aspect="connectivity",
                source_start=20,
            )
        ]
    )
    issue = result.blocking_issues[0]

    assert issue.cluster_id == "CL007"
    assert issue.aspect == "connectivity"
    assert issue.severity == 4
    assert issue.max_severity == 4
    assert issue.source_count == 4
    assert issue.independent_source_count == 4
    assert issue.domain_count == 4


def test_issue_ordering_is_stable() -> None:
    clusters = [
        cluster(1, 6, sentiment="negative", severity=4, source_start=1),
        cluster(2, 4, sentiment="negative", severity=5, source_start=20),
        cluster(3, 5, sentiment="negative", severity=5, source_start=30),
    ]

    first = decide(list(reversed(clusters)))
    second = decide(clusters)

    assert [issue.cluster_id for issue in first.blocking_issues] == [
        "CL003",
        "CL002",
        "CL001",
    ]
    assert first.blocking_issues == second.blocking_issues


def test_skip_sets_alternative_trigger_and_other_decisions_do_not() -> None:
    skip = decide([cluster(1, 4, sentiment="negative", severity=4)])
    buy = decide([cluster(1, 4, sentiment="positive")])

    assert skip.should_find_alternatives
    assert not buy.should_find_alternatives


@pytest.mark.parametrize(
    "value",
    ["BUY", "BUY_IF", "SKIP", "EARLY_ADOPTER"],
)
def test_all_purchase_decision_values_are_valid(value: str) -> None:
    assert PurchaseDecision(value).value == value


def test_invalid_purchase_decision_value_is_rejected() -> None:
    with pytest.raises(ValueError):
        PurchaseDecision("MAYBE")


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (0.399999, PurchaseDecision.EARLY_ADOPTER),
        (0.400000, PurchaseDecision.BUY),
        (0.400001, PurchaseDecision.BUY),
    ],
)
def test_confidence_threshold_boundary(score: float, expected: PurchaseDecision) -> None:
    result = decide(
        [cluster(1, 3, sentiment="neutral")],
        confidence(score, independent_sources=3),
    )

    assert result.decision is expected


@pytest.mark.parametrize(
    ("severity", "expected"),
    [
        (3, PurchaseDecision.BUY_IF),
        (4, PurchaseDecision.SKIP),
        (5, PurchaseDecision.SKIP),
    ],
)
def test_skip_severity_threshold_boundary(
    severity: int, expected: PurchaseDecision
) -> None:
    result = decide([cluster(1, 4, sentiment="negative", severity=severity)])

    assert result.decision is expected


@pytest.mark.parametrize(
    ("support", "expected"),
    [
        (3, PurchaseDecision.BUY_IF),
        (4, PurchaseDecision.SKIP),
        (5, PurchaseDecision.SKIP),
    ],
)
def test_skip_support_threshold_boundary(
    support: int, expected: PurchaseDecision
) -> None:
    result = decide([cluster(1, support, sentiment="negative", severity=4)])

    assert result.decision is expected


@pytest.mark.parametrize(
    ("independent_sources", "expected"),
    [
        (2, PurchaseDecision.EARLY_ADOPTER),
        (3, PurchaseDecision.BUY),
        (4, PurchaseDecision.BUY),
    ],
)
def test_evidence_independence_threshold_boundary(
    independent_sources: int, expected: PurchaseDecision
) -> None:
    result = decide(
        [cluster(1, max(3, independent_sources), sentiment="neutral")],
        confidence(0.4, independent_sources=independent_sources),
    )

    assert result.decision is expected


def test_policy_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValidationError, match="SKIP support threshold"):
        DecisionPolicy(
            skip_min_independent_support=2,
            buy_if_min_independent_support=3,
        )
    with pytest.raises(ValidationError, match="SKIP severity threshold"):
        DecisionPolicy(skip_min_severity=2, buy_if_min_severity=3)


def test_result_model_enforces_decision_invariants() -> None:
    with pytest.raises(ValidationError, match="BUY_IF requires"):
        PurchaseDecisionResult(
            decision=PurchaseDecision.BUY_IF,
            confidence_score=0.8,
            reasons=[DecisionReasonCode.CONDITIONAL_NEGATIVE_ISSUE],
            evidence_sufficient=True,
            should_find_alternatives=False,
        )
