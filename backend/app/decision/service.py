"""Stateless deterministic purchase-decision evaluation."""

from collections import defaultdict
from collections.abc import Iterable

from app.claim_clustering.models import ClaimCluster, ClaimClusteringResult
from app.confidence.exceptions import ConfidenceInputError
from app.confidence.models import ConfidenceLevel, ConfidenceResult
from app.confidence.service import EvidenceConfidenceEngine
from app.models import ClaimSentiment, PurchaseDecision
from app.source_filtering.models import IndependenceState

from .exceptions import DecisionInputError
from .models import DecisionReasonCode, DecisionSignal, PurchaseDecisionResult
from .policy import DecisionPolicy


class PurchaseDecisionEngine:
    def __init__(
        self,
        policy: DecisionPolicy = DecisionPolicy(),
        confidence_engine: EvidenceConfidenceEngine | None = None,
    ) -> None:
        self._policy = policy
        self._confidence_engine = confidence_engine or EvidenceConfidenceEngine()

    def evaluate(
        self,
        confidence: ConfidenceResult,
        clustering_result: ClaimClusteringResult,
    ) -> PurchaseDecisionResult:
        """Evaluate legacy unbound inputs; bound artifacts require evaluate_snapshot."""
        fields = (
            "analysis_id",
            "snapshot_id",
            "product_identity",
            "registry_id",
            "registry_revision",
        )
        if any(
            getattr(item, field) is not None
            for item in (confidence, clustering_result)
            for field in fields
        ):
            raise DecisionInputError(
                "snapshot-bound artifacts require evaluate_snapshot"
            )
        return self._evaluate(confidence, clustering_result)

    def _evaluate(
        self,
        confidence: ConfidenceResult,
        clustering_result: ClaimClusteringResult,
    ) -> PurchaseDecisionResult:
        clusters = clustering_result.clusters
        negative = [c for c in clusters if c.sentiment is ClaimSentiment.NEGATIVE]
        blocking = self._sorted_signals(
            self._signal(c, DecisionReasonCode.REPEATED_HIGH_SEVERITY_ISSUE)
            for c in negative if self._is_blocking(c)
        )
        conditions = self._sorted_signals(
            self._signal(c, DecisionReasonCode.LONG_TERM_NEGATIVE_ISSUE
                         if self._has_long_term_evidence(c)
                         else DecisionReasonCode.CONDITIONAL_NEGATIVE_ISSUE)
            for c in negative if self._is_conditional(c)
        )
        severe = self._sorted_signals(
            self._signal(c, DecisionReasonCode.UNRESOLVED_SEVERE_RISK)
            for c in negative if self._has_unresolved_severe_risk(c)
        )
        supporting = self._positive_signals(clusters)
        conflict_aspects = self._conflict_aspects(clusters)
        insufficiency = self._insufficiency_reasons(confidence, clusters)
        if insufficiency:
            return self._result(PurchaseDecision.EARLY_ADOPTER, confidence, insufficiency,
                                severe, supporting=supporting, sufficient=False)

        if blocking:
            reasons = [DecisionReasonCode.REPEATED_HIGH_SEVERITY_ISSUE]
            if any(issue.aspect in conflict_aspects for issue in blocking):
                reasons.append(DecisionReasonCode.CONFLICTING_EVIDENCE)
            blocked_ids = {signal.cluster_id for signal in blocking}
            unresolved = [signal for signal in severe if signal.cluster_id not in blocked_ids]
            return self._result(PurchaseDecision.SKIP, confidence, reasons, unresolved,
                                blocking=blocking, supporting=supporting, sufficient=True)

        if conditions:
            reasons = list(dict.fromkeys(issue.reason_code for issue in conditions))
            if any(issue.aspect in conflict_aspects for issue in conditions):
                reasons.append(DecisionReasonCode.CONFLICTING_EVIDENCE)
            condition_ids = {signal.cluster_id for signal in conditions}
            unresolved = [signal for signal in severe if signal.cluster_id not in condition_ids]
            return self._result(PurchaseDecision.BUY_IF, confidence, reasons, unresolved,
                                conditions=conditions, supporting=supporting, sufficient=True)

        if severe:
            return self._result(PurchaseDecision.EARLY_ADOPTER, confidence,
                                [DecisionReasonCode.UNRESOLVED_SEVERE_RISK], severe,
                                supporting=supporting, sufficient=False)

        conflicting = self._sorted_signals(
            self._signal(c, DecisionReasonCode.CONFLICTING_EVIDENCE)
            for c in negative if c.aspect in conflict_aspects
        )
        if conflicting:
            return self._result(PurchaseDecision.EARLY_ADOPTER, confidence,
                                [DecisionReasonCode.CONFLICTING_EVIDENCE], conflicting,
                                supporting=supporting, sufficient=False)
        if supporting:
            return self._result(
                PurchaseDecision.BUY, confidence,
                [DecisionReasonCode.NO_BLOCKING_ISSUES,
                 DecisionReasonCode.STRONG_POSITIVE_SUPPORT],
                [], supporting=supporting, sufficient=True,
            )
        return self._result(PurchaseDecision.EARLY_ADOPTER, confidence,
                            [DecisionReasonCode.NO_AFFIRMATIVE_SUPPORT], [],
                            sufficient=False)

    def evaluate_snapshot(
        self,
        snapshot,
        confidence: ConfidenceResult,
        clustering_result: ClaimClusteringResult,
    ) -> PurchaseDecisionResult:
        from app.claim_clustering.exceptions import SourceMetadataError
        from app.claim_clustering.service import SemanticClaimClusterer
        from app.claim_clustering.snapshot import (
            EvaluationSnapshot,
            SnapshotContractError,
        )

        try:
            validated = EvaluationSnapshot.validate_boundary(snapshot)
            validated_clusters = SemanticClaimClusterer.validate_snapshot_result(
                validated, clustering_result
            )
            validated_confidence = self._confidence_engine.validate_snapshot_result(
                validated, confidence, validated_clusters
            )
        except (
            SnapshotContractError,
            SourceMetadataError,
            ConfidenceInputError,
        ) as error:
            raise DecisionInputError(str(error)) from error
        return self._evaluate(validated_confidence, validated_clusters)
    @staticmethod
    def _result(decision, confidence, reasons, unresolved, *, blocking=None,
                conditions=None, supporting=None, sufficient=False):
        return PurchaseDecisionResult(
            decision=decision, confidence_score=confidence.overall_score,
            reasons=reasons, blocking_issues=blocking or [],
            conditions=conditions or [], unresolved_risks=unresolved,
            supporting_signals=supporting or [], evidence_sufficient=sufficient,
            should_find_alternatives=decision is PurchaseDecision.SKIP,
        )


    def _insufficiency_reasons(self, confidence, clusters):
        reasons = []
        if not clusters:
            reasons.append(DecisionReasonCode.NO_MEANINGFUL_CLAIMS)
        if not confidence.quality_gate_passed:
            reasons.append(DecisionReasonCode.INSUFFICIENT_EVIDENCE_QUALITY)
        if (confidence.overall_score < self._policy.minimum_evidence_confidence
                or confidence.confidence_level is ConfidenceLevel.LOW):
            reasons.append(DecisionReasonCode.LOW_EVIDENCE_CONFIDENCE)
        if confidence.metrics.independent_source_count < self._policy.minimum_independent_sources:
            reasons.append(DecisionReasonCode.INSUFFICIENT_INDEPENDENT_EVIDENCE)
        if reasons:
            reasons.insert(0, DecisionReasonCode.INSUFFICIENT_EVIDENCE)
        return reasons

    def _is_blocking(self, c):
        return sum(v >= self._policy.skip_min_severity
                   for v in self._group_severities(c, confirmed_only=True).values()
                   ) >= self._policy.skip_min_independent_support

    def _is_conditional(self, c):
        return sum(v >= self._policy.buy_if_min_severity
                   for v in self._group_severities(c, confirmed_only=True).values()
                   ) >= self._policy.buy_if_min_independent_support

    def _has_unresolved_severe_risk(self, c):
        return any(v >= self._policy.skip_min_severity for v in self._group_severities(c).values())

    def _has_long_term_evidence(self, c):
        return any(m >= self._policy.long_term_threshold_months for m in c.usage_period_months)

    @staticmethod
    def _group_severities(c, *, confirmed_only=False):
        confirmed = PurchaseDecisionEngine._confirmed_group_ids(c)
        values = {}
        for member in c.members:
            group = member.independence_group_id or member.claim.source_id
            if confirmed_only and group not in confirmed:
                continue
            values[group] = max(member.claim.severity, values.get(group, 0))
        return values

    def _severity(self, c):
        values = self._group_severities(c)
        return sum(values.values()) / len(values)

    @staticmethod
    def _confirmed_group_ids(c):
        if c.confirmed_independence_group_ids is not None:
            return set(c.confirmed_independence_group_ids)
        return {m.independence_group_id for m in c.members
                if m.independence_group_id is not None
                and m.independence_state is IndependenceState.CONFIRMED}

    def _conflict_aspects(self, clusters):
        groups = defaultdict(lambda: defaultdict(set))
        for c in clusters:
            groups[c.aspect][c.sentiment].update(self._confirmed_group_ids(c))
        threshold = self._policy.conflict_min_independent_support
        return {aspect for aspect, sentiments in groups.items()
                if len(sentiments[ClaimSentiment.POSITIVE]) >= threshold
                and len(sentiments[ClaimSentiment.NEGATIVE]) >= threshold}

    def _positive_signals(self, clusters):
        return self._sorted_signals(
            self._signal(c, DecisionReasonCode.STRONG_POSITIVE_SUPPORT)
            for c in clusters if c.sentiment is ClaimSentiment.POSITIVE
            and len(self._confirmed_group_ids(c)) >= self._policy.positive_min_independent_support
        )

    def _signal(self, c, reason):
        confirmed = self._group_severities(c, confirmed_only=True)
        return DecisionSignal(
            reason_code=reason, cluster_id=c.cluster_id, aspect=c.aspect,
            sentiment=c.sentiment, severity=self._severity(c), max_severity=c.max_severity,
            source_count=c.source_count,
            independent_source_count=len(self._confirmed_group_ids(c)),
            high_severity_independent_support=sum(
                value >= self._policy.skip_min_severity for value in confirmed.values()
            ),
            domain_count=c.domain_count, long_term_evidence=self._has_long_term_evidence(c),
        )

    @staticmethod
    def _sorted_signals(signals: Iterable[DecisionSignal]):
        return sorted(signals, key=lambda s: (-s.severity, -s.independent_source_count, s.cluster_id))
