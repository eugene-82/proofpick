"""Stateless deterministic purchase-decision evaluation."""

from collections import defaultdict
from collections.abc import Iterable

from app.claim_clustering.models import ClaimCluster, ClaimClusteringResult
from app.confidence.models import ConfidenceLevel, ConfidenceResult
from app.models import ClaimSentiment, PurchaseDecision

from .models import DecisionReasonCode, DecisionSignal, PurchaseDecisionResult
from .policy import DecisionPolicy


class PurchaseDecisionEngine:
    def __init__(self, policy: DecisionPolicy = DecisionPolicy()) -> None:
        self._policy = policy

    def evaluate(
        self,
        confidence: ConfidenceResult,
        clustering_result: ClaimClusteringResult,
    ) -> PurchaseDecisionResult:
        clusters = clustering_result.clusters
        insufficiency_reasons = self._insufficiency_reasons(confidence, clusters)
        if insufficiency_reasons:
            return PurchaseDecisionResult(
                decision=PurchaseDecision.EARLY_ADOPTER,
                confidence_score=confidence.overall_score,
                reasons=insufficiency_reasons,
                evidence_sufficient=False,
                should_find_alternatives=False,
            )

        conflict_aspects = self._conflict_aspects(clusters)
        negative_clusters = [
            cluster for cluster in clusters if cluster.sentiment is ClaimSentiment.NEGATIVE
        ]
        blocking = self._sorted_signals(
            self._signal(cluster, DecisionReasonCode.REPEATED_HIGH_SEVERITY_ISSUE)
            for cluster in negative_clusters
            if self._is_blocking(cluster)
        )
        if blocking:
            reasons = [DecisionReasonCode.REPEATED_HIGH_SEVERITY_ISSUE]
            if any(issue.aspect in conflict_aspects for issue in blocking):
                reasons.append(DecisionReasonCode.CONFLICTING_EVIDENCE)
            return PurchaseDecisionResult(
                decision=PurchaseDecision.SKIP,
                confidence_score=confidence.overall_score,
                reasons=reasons,
                blocking_issues=blocking,
                supporting_signals=self._positive_signals(clusters),
                evidence_sufficient=True,
                should_find_alternatives=True,
            )

        conditions = self._sorted_signals(
            self._signal(
                cluster,
                DecisionReasonCode.LONG_TERM_NEGATIVE_ISSUE
                if self._has_long_term_evidence(cluster)
                else DecisionReasonCode.CONDITIONAL_NEGATIVE_ISSUE,
            )
            for cluster in negative_clusters
            if self._is_conditional(cluster)
        )
        if conditions:
            reasons = list(dict.fromkeys(issue.reason_code for issue in conditions))
            if any(issue.aspect in conflict_aspects for issue in conditions):
                reasons.append(DecisionReasonCode.CONFLICTING_EVIDENCE)
            return PurchaseDecisionResult(
                decision=PurchaseDecision.BUY_IF,
                confidence_score=confidence.overall_score,
                reasons=reasons,
                conditions=conditions,
                supporting_signals=self._positive_signals(clusters),
                evidence_sufficient=True,
                should_find_alternatives=False,
            )

        supporting = self._positive_signals(clusters)
        reasons = [DecisionReasonCode.NO_BLOCKING_ISSUES]
        if supporting:
            reasons.append(DecisionReasonCode.STRONG_POSITIVE_SUPPORT)
        return PurchaseDecisionResult(
            decision=PurchaseDecision.BUY,
            confidence_score=confidence.overall_score,
            reasons=reasons,
            supporting_signals=supporting,
            evidence_sufficient=True,
            should_find_alternatives=False,
        )

    def _insufficiency_reasons(
        self,
        confidence: ConfidenceResult,
        clusters: list[ClaimCluster],
    ) -> list[DecisionReasonCode]:
        reasons: list[DecisionReasonCode] = []
        if not clusters:
            reasons.append(DecisionReasonCode.NO_MEANINGFUL_CLAIMS)
        if (
            confidence.overall_score < self._policy.minimum_evidence_confidence
            or confidence.confidence_level is ConfidenceLevel.LOW
        ):
            reasons.append(DecisionReasonCode.LOW_EVIDENCE_CONFIDENCE)
        if confidence.metrics.independent_source_count < self._policy.minimum_independent_sources:
            reasons.append(DecisionReasonCode.INSUFFICIENT_INDEPENDENT_EVIDENCE)
        if reasons:
            reasons.insert(0, DecisionReasonCode.INSUFFICIENT_EVIDENCE)
        return reasons

    def _is_blocking(self, cluster: ClaimCluster) -> bool:
        return (
            self._severity(cluster) >= self._policy.skip_min_severity
            and cluster.independent_source_count
            >= self._policy.skip_min_independent_support
        )

    def _is_conditional(self, cluster: ClaimCluster) -> bool:
        return (
            self._severity(cluster) >= self._policy.buy_if_min_severity
            and cluster.independent_source_count
            >= self._policy.buy_if_min_independent_support
        )

    def _has_long_term_evidence(self, cluster: ClaimCluster) -> bool:
        return any(
            months >= self._policy.long_term_threshold_months
            for months in cluster.usage_period_months
        )

    @staticmethod
    def _severity(cluster: ClaimCluster) -> float:
        severity_by_source: dict[str, int] = {}
        for member in cluster.members:
            source_id = member.claim.source_id
            severity_by_source[source_id] = max(
                member.claim.severity, severity_by_source.get(source_id, 0)
            )
        return sum(severity_by_source.values()) / len(severity_by_source)

    def _conflict_aspects(self, clusters: list[ClaimCluster]) -> set[str]:
        groups: dict[str, dict[ClaimSentiment, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        for cluster in clusters:
            groups[cluster.aspect][cluster.sentiment].update(
                cluster.independence_group_ids
            )
        threshold = self._policy.conflict_min_independent_support
        return {
            aspect
            for aspect, by_sentiment in groups.items()
            if len(by_sentiment[ClaimSentiment.POSITIVE]) >= threshold
            and len(by_sentiment[ClaimSentiment.NEGATIVE]) >= threshold
        }

    def _positive_signals(self, clusters: list[ClaimCluster]) -> list[DecisionSignal]:
        return self._sorted_signals(
            self._signal(cluster, DecisionReasonCode.STRONG_POSITIVE_SUPPORT)
            for cluster in clusters
            if cluster.sentiment is ClaimSentiment.POSITIVE
            and cluster.independent_source_count
            >= self._policy.positive_min_independent_support
        )

    def _signal(
        self,
        cluster: ClaimCluster,
        reason_code: DecisionReasonCode,
    ) -> DecisionSignal:
        return DecisionSignal(
            reason_code=reason_code,
            cluster_id=cluster.cluster_id,
            aspect=cluster.aspect,
            sentiment=cluster.sentiment,
            severity=self._severity(cluster),
            max_severity=cluster.max_severity,
            source_count=cluster.source_count,
            independent_source_count=cluster.independent_source_count,
            domain_count=cluster.domain_count,
            long_term_evidence=self._has_long_term_evidence(cluster),
        )

    @staticmethod
    def _sorted_signals(signals: Iterable[DecisionSignal]) -> list[DecisionSignal]:
        return sorted(
            signals,
            key=lambda signal: (
                -signal.severity,
                -signal.independent_source_count,
                signal.cluster_id,
            ),
        )
