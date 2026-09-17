from app.analysis_runtime import CounterEvidenceQueryGenerator
from app.claim_clustering.models import ClaimClusteringResult
from app.decision.models import (
    DecisionReasonCode,
    DecisionSignal,
    PurchaseDecisionResult,
)
from app.models import ClaimSentiment, PurchaseDecision


def decision_signal() -> DecisionSignal:
    return DecisionSignal(
        reason_code=DecisionReasonCode.REPEATED_HIGH_SEVERITY_ISSUE,
        cluster_id="CL001",
        aspect="battery_health",
        sentiment=ClaimSentiment.NEGATIVE,
        severity=5,
        max_severity=5,
        source_count=4,
        independent_source_count=4,
        high_severity_independent_support=4,
        domain_count=4,
        long_term_evidence=True,
    )


def result(decision: PurchaseDecision) -> PurchaseDecisionResult:
    if decision is PurchaseDecision.SKIP:
        return PurchaseDecisionResult(
            decision=decision,
            confidence_score=0.8,
            reasons=[DecisionReasonCode.REPEATED_HIGH_SEVERITY_ISSUE],
            blocking_issues=[decision_signal()],
            evidence_sufficient=True,
            should_find_alternatives=True,
        )
    if decision is PurchaseDecision.BUY_IF:
        condition = decision_signal().model_copy(
            update={
                "reason_code": DecisionReasonCode.CONDITIONAL_NEGATIVE_ISSUE,
            }
        )
        return PurchaseDecisionResult(
            decision=decision,
            confidence_score=0.6,
            reasons=[DecisionReasonCode.CONDITIONAL_NEGATIVE_ISSUE],
            conditions=[condition],
            evidence_sufficient=True,
            should_find_alternatives=False,
        )
    return PurchaseDecisionResult(
        decision=decision,
        confidence_score=0.8 if decision is PurchaseDecision.BUY else 0.2,
        reasons=[
            DecisionReasonCode.STRONG_POSITIVE_SUPPORT
            if decision is PurchaseDecision.BUY
            else DecisionReasonCode.INSUFFICIENT_EVIDENCE
        ],
        evidence_sufficient=decision is not PurchaseDecision.EARLY_ADOPTER,
        should_find_alternatives=False,
    )


def generate(
    decision: PurchaseDecision,
    *,
    initial_queries: tuple[str, ...] = (),
):
    return CounterEvidenceQueryGenerator().generate(
        product_identity="Example Headphones",
        decision=result(decision),
        clusters=ClaimClusteringResult(),
        initial_queries=initial_queries,
    )


def test_buy_generates_negative_problem_queries() -> None:
    plan = generate(PurchaseDecision.BUY)

    assert plan.queries == (
        "Example Headphones problems long term",
        "Example Headphones failure issue",
    )


def test_buy_if_also_generates_negative_problem_queries() -> None:
    assert generate(PurchaseDecision.BUY_IF).queries == (
        "Example Headphones problems long term",
        "Example Headphones failure issue",
    )


def test_skip_generates_contrary_context_queries_from_blocking_aspect() -> None:
    plan = generate(PurchaseDecision.SKIP)

    assert plan.queries == (
        "Example Headphones battery health no issue long term",
        "Example Headphones battery health fixed resolved",
        "Example Headphones long term positive",
    )


def test_early_adopter_skips_counter_search() -> None:
    assert generate(PurchaseDecision.EARLY_ADOPTER).queries == ()


def test_queries_are_deduplicated_against_initial_plan() -> None:
    plan = generate(
        PurchaseDecision.BUY,
        initial_queries=(
            "  example   headphones PROBLEMS long term ",
        ),
    )

    assert plan.queries == ("Example Headphones failure issue",)


def test_query_order_is_deterministic_and_bounded() -> None:
    first = generate(PurchaseDecision.SKIP)
    second = generate(PurchaseDecision.SKIP)

    assert first == second
    assert len(first.queries) <= 3


def test_global_budget_can_prevent_counter_queries() -> None:
    initial = tuple(f"query {index}" for index in range(10))

    assert generate(PurchaseDecision.BUY, initial_queries=initial).queries == ()
