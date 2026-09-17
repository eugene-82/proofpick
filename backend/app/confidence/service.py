"""Deterministic and inspectable evidence-confidence calculation."""

from collections import defaultdict
from collections.abc import Iterable
from math import exp

from pydantic import ValidationError

from app.claim_clustering.models import ClaimCluster, ClaimClusteringResult
from app.claim_clustering.service import SemanticClaimClusterer
from app.claim_clustering.exceptions import SourceMetadataError
from app.claim_extraction.models import ObservationType
from app.evidence_processing.models import EvidenceQuality, ObservationState
from app.models import ClaimSentiment
from app.source_filtering.models import FilteredSource, IndependenceState

from .exceptions import ConfidenceInputError
from .models import (
    ConfidenceComponentBreakdown,
    ConfidenceEvidenceMetrics,
    ConfidenceLevel,
    ConfidenceQualityIssue,
    ConfidenceResult,
    ConfidenceSourceMetadata,
)
from .policy import ConfidencePolicy


class EvidenceConfidenceEngine:
    """Score evidence reliability without judging whether a product is good."""

    def __init__(self, policy: ConfidencePolicy = ConfidencePolicy()) -> None:
        self._policy = policy

    def evaluate(
        self,
        clustering_result: ClaimClusteringResult,
        sources: Iterable[ConfidenceSourceMetadata | FilteredSource],
    ) -> ConfidenceResult:
        """Evaluate legacy unbound inputs; snapshot-bound artifacts use evaluate_snapshot."""
        try:
            validated_result = ClaimClusteringResult.model_validate(
                clustering_result.model_dump(mode="python", warnings=False)
            )
        except (AttributeError, TypeError, ValueError, ValidationError) as error:
            raise ConfidenceInputError("invalid cluster result schema") from error
        lineage_fields = (
            "analysis_id",
            "snapshot_id",
            "product_identity",
            "registry_id",
            "registry_revision",
            "input_snapshot_digest",
            "input_claim_manifest",
            "provenance_manifest",
            "content_digest",
        )
        if any(getattr(validated_result, field) is not None for field in lineage_fields):
            raise ConfidenceInputError(
                "snapshot-bound clusters require evaluate_snapshot"
            )
        return self._evaluate(validated_result, sources)

    def _evaluate(
        self,
        clustering_result: ClaimClusteringResult,
        sources: Iterable[ConfidenceSourceMetadata | FilteredSource],
    ) -> ConfidenceResult:
        clusters = clustering_result.clusters
        if not clusters:
            return self._empty_result(clustering_result)

        source_by_id = self._source_lookup(sources)
        used_source_ids = list(
            dict.fromkeys(
                source_id
                for cluster in clusters
                for source_id in cluster.source_ids
            )
        )
        missing = [source_id for source_id in used_source_ids if source_id not in source_by_id]
        if missing:
            raise ConfidenceInputError(
                f"source metadata missing for: {', '.join(sorted(missing))}"
            )

        used_sources = [source_by_id[source_id] for source_id in used_source_ids]
        self._validate_cluster_provenance(clusters, source_by_id)
        source_count = len(used_sources)
        used_group_ids = {
            source.independence_group_id for source in used_sources
        }
        confirmed_registry_groups = {
            source.independence_group_id
            for source in source_by_id.values()
            if source.independence_state is IndependenceState.CONFIRMED
        }
        independence_groups = used_group_ids & confirmed_registry_groups
        domains = {source.domain.casefold() for source in used_sources}

        volume = self._saturating(source_count, self._policy.volume_saturation_scale)
        independence = self._independence_score(
            source_count, len(independence_groups)
        )
        diversity = self._saturating(
            len(domains), self._policy.diversity_saturation_scale
        )
        agreement = self._agreement_score(clusters)
        long_term, long_term_sources, long_term_groups = self._long_term_score(
            clusters, source_by_id, independence_groups
        )
        commercial_risk, commercial_group_count = self._commercial_risk(
            used_sources, independence_groups
        )
        commercial_penalty = commercial_risk * self._policy.commercial_risk_weight

        overall = (
            volume * self._policy.evidence_volume_weight
            + independence * self._policy.independence_weight
            + diversity * self._policy.diversity_weight
            + agreement * self._policy.agreement_weight
            + long_term * self._policy.long_term_weight
            - commercial_penalty
        )
        overall = self._clamp(overall)
        if len(independence_groups) <= 1:
            overall = min(overall, self._policy.single_independent_source_cap)
        overall = self._rounded(overall)
        quality_issues = self._quality_issues(
            clusters, used_sources, list(source_by_id.values())
        )
        level = self._level(overall)
        if quality_issues and level is ConfidenceLevel.HIGH:
            level = ConfidenceLevel.MEDIUM

        return ConfidenceResult(
            overall_score=overall,
            confidence_level=level,
            components=ConfidenceComponentBreakdown(
                evidence_volume_score=self._rounded(volume),
                independence_score=self._rounded(independence),
                diversity_score=self._rounded(diversity),
                agreement_score=self._rounded(agreement),
                long_term_score=self._rounded(long_term),
                commercial_risk_score=self._rounded(commercial_risk),
            ),
            commercial_risk_penalty=self._rounded(commercial_penalty),
            metrics=ConfidenceEvidenceMetrics(
                cluster_count=len(clusters),
                source_count=source_count,
                independent_source_count=len(independence_groups),
                domain_count=len(domains),
                long_term_source_count=len(long_term_sources),
                long_term_independent_source_count=len(long_term_groups),
                commercial_signal_group_count=commercial_group_count,
            ),
            quality_gate_passed=not quality_issues,
            quality_issues=quality_issues,
            analysis_id=clustering_result.analysis_id,
            snapshot_id=clustering_result.snapshot_id,
            product_identity=clustering_result.product_identity,
            registry_id=clustering_result.registry_id,
            registry_revision=clustering_result.registry_revision,
        )

    @staticmethod
    def _quality_issues(
        clusters: list[ClaimCluster],
        sources: list[ConfidenceSourceMetadata],
        coverage_sources: list[ConfidenceSourceMetadata],
    ) -> list[ConfidenceQualityIssue]:
        issues: list[ConfidenceQualityIssue] = []
        if sources and all(
            source.evidence_quality is EvidenceQuality.SNIPPET_ONLY for source in sources
        ):
            issues.append(ConfidenceQualityIssue.SNIPPET_ONLY_COVERAGE)
        if sum(source.verified_claim_count for source in sources) == 0:
            issues.append(ConfidenceQualityIssue.NO_VERIFIED_CLAIM_COVERAGE)
        if sources and any(
            source.evidence_quality is EvidenceQuality.UNKNOWN for source in sources
        ):
            issues.append(ConfidenceQualityIssue.UNKNOWN_SOURCE_QUALITY)
        durability_aspects = {
            "battery", "battery_health", "battery_life", "durability", "reliability"
        }
        if any(source.evidence_coverage_limited for source in coverage_sources):
            issues.append(ConfidenceQualityIssue.UNSAFE_PARTIAL_EVIDENCE)
        durability_clusters = [
            cluster for cluster in clusters
            if cluster.aspect in durability_aspects
            and cluster.sentiment is ClaimSentiment.POSITIVE
        ]
        durability_source_ids = {
            source_id
            for cluster in durability_clusters
            for source_id in cluster.source_ids
        }
        durability_sources = [
            source for source in sources
            if source.source_id in durability_source_ids
        ]
        if durability_clusters and not any(
            source.observation_state is ObservationState.ESTABLISHED
            for source in durability_sources
        ):
            issues.append(ConfidenceQualityIssue.INSUFFICIENT_DURABILITY_OBSERVATION)
        return issues

    @staticmethod
    def _source_lookup(
        sources: Iterable[ConfidenceSourceMetadata | FilteredSource],
    ) -> dict[str, ConfidenceSourceMetadata]:
        lookup: dict[str, ConfidenceSourceMetadata] = {}
        for source in sources:
            raw_metadata = (
                source
                if isinstance(source, ConfidenceSourceMetadata)
                else ConfidenceSourceMetadata.from_filtered_source(source)
            )
            try:
                metadata = ConfidenceSourceMetadata.model_validate(
                    raw_metadata.model_dump(mode="python", warnings=False)
                )
            except (AttributeError, TypeError, ValueError, ValidationError) as error:
                raise ConfidenceInputError("invalid source metadata schema") from error
            if metadata.source_id in lookup:
                raise ConfidenceInputError(
                    f"duplicate source metadata for {metadata.source_id}"
                )
            lookup[metadata.source_id] = metadata
        return lookup

    @staticmethod
    def _validate_cluster_provenance(
        clusters: list[ClaimCluster],
        source_by_id: dict[str, ConfidenceSourceMetadata],
    ) -> None:
        confirmed_registry_groups = {
            source.independence_group_id
            for source in source_by_id.values()
            if source.independence_state is IndependenceState.CONFIRMED
        }
        unknown_registry_groups = {
            source.independence_group_id
            for source in source_by_id.values()
            if source.independence_state is IndependenceState.UNKNOWN
        }
        for cluster in clusters:
            metadata = [source_by_id[source_id] for source_id in cluster.source_ids]
            groups = {source.independence_group_id for source in metadata}
            confirmed_groups = groups & confirmed_registry_groups
            unknown_groups = (groups & unknown_registry_groups) - confirmed_groups
            domains = {source.domain.casefold() for source in metadata}
            if groups != set(cluster.independence_group_ids):
                raise ConfidenceInputError(
                    f"independence metadata disagrees with {cluster.cluster_id}"
                )
            if (
                cluster.confirmed_independence_group_ids is not None
                and confirmed_groups != set(cluster.confirmed_independence_group_ids)
            ):
                raise ConfidenceInputError(
                    f"confirmed independence metadata disagrees with {cluster.cluster_id}"
                )
            if (
                cluster.unknown_independence_group_ids is not None
                and unknown_groups
                != set(cluster.unknown_independence_group_ids)
            ):
                raise ConfidenceInputError(
                    f"unknown independence metadata disagrees with {cluster.cluster_id}"
                )
            if domains != {domain.casefold() for domain in cluster.domains}:
                raise ConfidenceInputError(
                    f"domain metadata disagrees with {cluster.cluster_id}"
                )

    def _independence_score(self, source_count: int, group_count: int) -> float:
        if source_count == 0:
            return 0.0
        absolute = self._saturating(
            group_count, self._policy.independence_saturation_scale
        )
        ratio = group_count / source_count
        share = self._policy.independence_absolute_share
        return share * absolute + (1.0 - share) * ratio

    def _agreement_score(self, clusters: list[ClaimCluster]) -> float:
        sentiment_groups: dict[str, dict[ClaimSentiment, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        for cluster in clusters:
            sentiment_groups[cluster.aspect][cluster.sentiment].update(
                cluster.independence_group_ids
            )

        conflict_factors: dict[str, float] = {}
        for aspect, by_sentiment in sentiment_groups.items():
            positive = len(by_sentiment[ClaimSentiment.POSITIVE])
            negative = len(by_sentiment[ClaimSentiment.NEGATIVE])
            polarized_total = positive + negative
            conflict_factors[aspect] = (
                max(positive, negative) / polarized_total
                if positive and negative
                else 1.0
            )

        weighted_score = 0.0
        total_weight = 0
        for cluster in clusters:
            support = cluster.independent_source_count
            strength = self._saturating(
                support, self._policy.agreement_saturation_scale
            )
            weighted_score += strength * support * conflict_factors[cluster.aspect]
            total_weight += support
        return weighted_score / total_weight if total_weight else 0.0

    def _long_term_score(
        self,
        clusters: list[ClaimCluster],
        source_by_id: dict[str, ConfidenceSourceMetadata],
        confirmed_group_ids: set[str],
    ) -> tuple[float, set[str], set[str]]:
        months_by_source: dict[str, int] = {}
        for cluster in clusters:
            for member in cluster.members:
                months = member.claim.usage_period_months
                if months is not None and months >= self._policy.long_term_threshold_months:
                    months_by_source[member.claim.source_id] = max(
                        months,
                        months_by_source.get(member.claim.source_id, 0),
                    )
        if not months_by_source:
            return 0.0, set(), set()

        months_by_group: dict[str, int] = {}
        for source_id, months in months_by_source.items():
            source = source_by_id[source_id]
            group_id = source.independence_group_id
            if group_id not in confirmed_group_ids:
                continue
            months_by_group[group_id] = max(months, months_by_group.get(group_id, 0))

        if not months_by_group:
            return 0.0, set(months_by_source), set()
        group_count = len(months_by_group)
        absolute = self._saturating(
            group_count, self._policy.long_term_saturation_scale
        )
        total_group_count = len(confirmed_group_ids)
        coverage = group_count / total_group_count if total_group_count else 0.0
        duration = sum(
            min(months / self._policy.long_term_target_months, 1.0)
            for months in months_by_group.values()
        ) / group_count
        score = (
            self._policy.long_term_absolute_share * absolute
            + self._policy.long_term_coverage_share * coverage
            + self._policy.long_term_duration_share * duration
        )
        return self._clamp(score), set(months_by_source), set(months_by_group)

    @staticmethod
    def _commercial_risk(
        sources: list[ConfidenceSourceMetadata],
        confirmed_group_ids: set[str],
    ) -> tuple[float, int]:
        signals_by_group: dict[str, list[float]] = defaultdict(list)
        for source in sources:
            if (
                source.independence_group_id in confirmed_group_ids
                and source.commercial_signal is not None
            ):
                signals_by_group[source.independence_group_id].append(
                    source.commercial_signal
                )
        if not signals_by_group:
            return 0.0, 0
        group_signals = [max(signals) for signals in signals_by_group.values()]
        return sum(group_signals) / len(group_signals), len(group_signals)

    def _level(self, score: float) -> ConfidenceLevel:
        if score >= self._policy.high_threshold:
            return ConfidenceLevel.HIGH
        if score >= self._policy.medium_threshold:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW

    def _empty_result(self, clustering_result: ClaimClusteringResult) -> ConfidenceResult:
        return ConfidenceResult(
            overall_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            components=ConfidenceComponentBreakdown(
                evidence_volume_score=0.0,
                independence_score=0.0,
                diversity_score=0.0,
                agreement_score=0.0,
                long_term_score=0.0,
                commercial_risk_score=0.0,
            ),
            commercial_risk_penalty=0.0,
            metrics=ConfidenceEvidenceMetrics(
                cluster_count=0,
                source_count=0,
                independent_source_count=0,
                domain_count=0,
                long_term_source_count=0,
                long_term_independent_source_count=0,
                commercial_signal_group_count=0,
            ),
            analysis_id=clustering_result.analysis_id,
            snapshot_id=clustering_result.snapshot_id,
            product_identity=clustering_result.product_identity,
            registry_id=clustering_result.registry_id,
            registry_revision=clustering_result.registry_revision,
        )

    def evaluate_snapshot(
        self,
        snapshot,
        clustering_result: ClaimClusteringResult,
    ) -> ConfidenceResult:
        from app.claim_clustering.snapshot import (
            EvaluationSnapshot,
            SnapshotContractError,
        )

        try:
            validated = EvaluationSnapshot.validate_boundary(snapshot)
        except SnapshotContractError as error:
            raise ConfidenceInputError(str(error)) from error
        try:
            validated_clusters = SemanticClaimClusterer.validate_snapshot_result(
                validated, clustering_result
            )
        except SourceMetadataError as error:
            raise ConfidenceInputError(str(error)) from error
        verified_counts: dict[str, int] = defaultdict(int)
        relations_by_source: dict[str, list] = defaultdict(list)
        for assessment in validated.grounding_assessments:
            verified_counts[assessment.claim.source_id] += 1
            relations_by_source[assessment.claim.source_id].append(
                assessment.semantic_relation
            )
        metadata = []
        for document in validated.evidence_documents:
            item = ConfidenceSourceMetadata.from_evidence_document(
                document,
                verified_claim_count=verified_counts[document.source_key],
                extracted_claim_count=verified_counts[document.source_key],
            )
            item = item.model_copy(
                update={
                    "observation_state": self._semantic_observation_state(
                        relations_by_source[document.source_key]
                    )
                }
            )
            metadata.append(item)
        result = self._evaluate(validated_clusters, metadata)
        result = result.model_copy(
            update={
                "input_snapshot_digest": validated.snapshot_id,
                "input_cluster_digest": validated_clusters.content_digest,
                "provenance_manifest": validated.registry_manifest,
            }
        )
        return result.model_copy(
            update={"content_digest": result.expected_content_digest()}
        )

    def validate_snapshot_result(
        self,
        snapshot,
        confidence: ConfidenceResult,
        clustering_result: ClaimClusteringResult,
    ) -> ConfidenceResult:
        """Recompute and compare a snapshot-bound confidence artifact."""
        try:
            validated_confidence = ConfidenceResult.model_validate(
                confidence.model_dump(mode="python", warnings=False)
            )
        except (AttributeError, TypeError, ValueError, ValidationError) as error:
            raise ConfidenceInputError("invalid confidence result schema") from error
        expected = self.evaluate_snapshot(snapshot, clustering_result)
        if (
            validated_confidence.model_dump(mode="json")
            != expected.model_dump(mode="json")
        ):
            raise ConfidenceInputError(
                "confidence result is not the deterministic snapshot result"
            )
        return validated_confidence

    @staticmethod
    def _semantic_observation_state(relations) -> ObservationState:
        observed = {
            ObservationType.USAGE,
            ObservationType.OWNERSHIP,
            ObservationType.TEST,
        }
        if any(
            relation is not None
            and relation.observation_type in observed
            and relation.observation_months is not None
            for relation in relations
        ):
            return ObservationState.ESTABLISHED
        if any(
            relation is not None
            and (
                relation.observation_type is ObservationType.FIRST_IMPRESSION
                or relation.observation_type in observed
            )
            for relation in relations
        ):
            return ObservationState.FIRST_IMPRESSION
        return ObservationState.UNKNOWN

    @staticmethod
    def _saturating(count: int, scale: float) -> float:
        return 0.0 if count <= 0 else 1.0 - exp(-count / scale)

    @staticmethod
    def _clamp(value: float) -> float:
        return min(max(value, 0.0), 1.0)

    @staticmethod
    def _rounded(value: float) -> float:
        return round(value, 6)
