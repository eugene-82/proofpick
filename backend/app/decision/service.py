"""Stateless deterministic purchase-decision evaluation."""

from collections import defaultdict
from collections.abc import Iterable

from app.claim_clustering.models import ClaimCluster, ClaimClusteringResult
from app.confidence.models import ConfidenceLevel, ConfidenceResult
from app.models import ClaimSentiment, PurchaseDecision
from app.source_filtering.models import IndependenceState

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

        severe_risks = self._sorted_signals(
            self._signal(cluster, DecisionReasonCode.UNRESOLVED_SEVERE_RISK)
            for cluster in negative_clusters
            if self._has_unresolved_severe_risk(cluster)
        )
        if severe_risks:
            return PurchaseDecisionResult(
                decision=PurchaseDecision.EARLY_ADOPTER,
                confidence_score=confidence.overall_score,
                reasons=[DecisionReasonCode.UNRESOLVED_SEVERE_RISK],
                unresolved_risks=severe_risks,
                supporting_signals=self._positive_signals(clusters),
                evidence_sufficient=False,
                should_find_alternatives=False,
            )

        conflicting_risks = self._sorted_signals(
            self._signal(cluster, DecisionReasonCode.CONFLICTING_EVIDENCE)
            for cluster in negative_clusters
            if cluster.aspect in conflict_aspects
        )
        if conflicting_risks:
            return PurchaseDecisionResult(
                decision=PurchaseDecision.EARLY_ADOPTER,
                confidence_score=confidence.overall_score,
                reasons=[DecisionReasonCode.CONFLICTING_EVIDENCE],
                unresolved_risks=conflicting_risks,
                supporting_signals=self._positive_signals(clusters),
                evidence_sufficient=False,
                should_find_alternatives=False,
            )

        supporting = self._positive_signals(clusters)
        if supporting:
            return PurchaseDecisionResult(
                decision=PurchaseDecision.BUY,
                confidence_score=confidence.overall_score,
                reasons=[
                    DecisionReasonCode.NO_BLOCKING_ISSUES,
                    DecisionReasonCode.STRONG_POSITIVE_SUPPORT,
                ],
                supporting_signals=supporting,
                evidence_sufficient=True,
                should_find_alternatives=False,
            )

        return PurchaseDecisionResult(
            decision=PurchaseDecision.EARLY_ADOPTER,
            confidence_score=confidence.overall_score,
            reasons=[DecisionReasonCode.NO_AFFIRMATIVE_SUPPORT],
            evidence_sufficient=False,
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
        severe_groups = sum(
            severity >= self._policy.skip_min_severity
            for severity in self._group_severities(cluster, confirmed_only=True).values()
        )
        return severe_groups >= self._policy.skip_min_independent_support

    def _is_conditional(self, cluster: ClaimCluster) -> bool:
        affected_groups = sum(
            severity >= self._policy.buy_if_min_severity
            for severity in self._group_severities(cluster, confirmed_only=True).values()
        )
        return affected_groups >= self._policy.buy_if_min_independent_support

    def _has_unresolved_severe_risk(self, cluster: ClaimCluster) -> bool:
        return any(
            severity >= self._policy.skip_min_severity
            for severity in self._group_severities(cluster).values()
        )

    def _has_long_term_evidence(self, cluster: ClaimCluster) -> bool:
        return any(
            months >= self._policy.long_term_threshold_months
            for months in cluster.usage_period_months
        )

    @staticmethod
    def _group_severities(
        cluster: ClaimCluster,
        *,
        confirmed_only: bool = False,
    ) -> dict[str, int]:
        confirmed_groups = PurchaseDecisionEngine._confirmed_group_ids(cluster)
        severities: dict[str, int] = {}
        for member in cluster.members:
            group_id = member.independence_group_id or member.claim.source_id
            if confirmed_only and group_id not in confirmed_groups:
                continue
            severities[group_id] = max(
                member.claim.severity,
                severities.get(group_id, 0),
            )
        return severities

    def _severity(self, cluster: ClaimCluster) -> float:
        severities = self._group_severities(cluster)
        return sum(severities.values()) / len(severities)

    @staticmethod
    def _confirmed_group_ids(cluster: ClaimCluster) -> set[str]:
        if cluster.confirmed_independence_group_ids is not None:
            return set(cluster.confirmed_independence_group_ids)
        return {
            member.independence_group_id
            for member in cluster.members
            if member.independence_group_id is not None
            and member.independence_state is IndependenceState.CONFIRMED
        }

    def _conflict_aspects(self, clusters: list[ClaimCluster]) -> set[str]:
        groups: dict[str, dict[ClaimSentiment, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        for cluster in clusters:
            groups[cluster.aspect][cluster.sentiment].update(
                self._confirmed_group_ids(cluster)
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
            and len(self._confirmed_group_ids(cluster))
            >= self._policy.positive_min_independent_support
        )

    def _signal(
        self,
        cluster: ClaimCluster,
        reason_code: DecisionReasonCode,
    ) -> DecisionSignal:
        confirmed_severities = self._group_severities(cluster, confirmed_only=True)
        return DecisionSignal(
            reason_code=reason_code,
            cluster_id=cluster.cluster_id,
            aspect=cluster.aspect,
            sentiment=cluster.sentiment,
            severity=self._severity(cluster),
            max_severity=cluster.max_severity,
            source_count=cluster.source_count,
            independent_source_count=len(self._confirmed_group_ids(cluster)),
            high_severity_independent_support=sum(
                severity >= self._policy.skip_min_severity
                for severity in confirmed_severities.values()
            ),
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
