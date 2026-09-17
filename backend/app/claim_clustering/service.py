"""Deterministic semantic claim clustering with complete provenance."""

from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256

from pydantic import ValidationError

from app.claim_extraction.models import ExtractedClaim
from app.integrity import canonical_digest
from app.source_filtering.models import FilteredSource

from .base import EmbeddingProvider
from .exceptions import EmbeddingValidationError, SourceMetadataError
from .models import (
    ClaimCluster,
    ClaimClusteringResult,
    ClusterMember,
)
from .policy import ClaimClusteringPolicy
from .similarity import cosine_similarity, normalize_vector


ASPECT_ALIASES = {
    "battery_health": "battery",
    "battery_duration": "battery",
    "battery_life": "battery",
    "battery_runtime": "battery",
    "connection": "connectivity",
}


@dataclass(frozen=True)
class _ClaimRecord:
    index: int
    claim_id: str
    claim: ExtractedClaim
    aspect: str
    embedding_text: str
    embedding_key: str
    vector: tuple[float, ...]


class SemanticClaimClusterer:
    """Group same-aspect, same-sentiment claims with pairwise coherence."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        policy: ClaimClusteringPolicy = ClaimClusteringPolicy(),
    ) -> None:
        self._provider = provider
        self._policy = policy
        self._embedding_cache: dict[str, tuple[float, ...]] = {}
        self._embedding_dimension: int | None = None

    def cluster(
        self,
        claims: Iterable[ExtractedClaim],
        sources: Iterable[FilteredSource],
    ) -> ClaimClusteringResult:
        claim_list = sorted(
            claims,
            key=lambda claim: (
                ASPECT_ALIASES.get(claim.aspect, claim.aspect),
                claim.sentiment.value,
                " ".join(claim.claim.casefold().split()),
                claim.source_id,
                " ".join(claim.evidence_fragment.casefold().split()),
                claim.severity,
                claim.usage_period_months or 0,
            ),
        )
        if not claim_list:
            return ClaimClusteringResult()

        source_by_id = self._source_lookup(sources)
        missing_sources = sorted(
            {claim.source_id for claim in claim_list if claim.source_id not in source_by_id}
        )
        if missing_sources:
            raise SourceMetadataError(
                f"source metadata missing for: {', '.join(missing_sources)}"
            )

        records = self._records_with_embeddings(claim_list)
        partitions: dict[tuple[str, str], list[_ClaimRecord]] = defaultdict(list)
        for record in records:
            partitions[(record.aspect, record.claim.sentiment.value)].append(record)

        components: list[list[_ClaimRecord]] = []
        for partition_records in partitions.values():
            components.extend(self._complete_link_clusters(partition_records))
        components.sort(key=lambda component: min(record.index for record in component))

        clusters = [
            self._build_cluster(cluster_index, component, source_by_id)
            for cluster_index, component in enumerate(components, start=1)
        ]
        return ClaimClusteringResult(clusters=clusters)

    def cluster_snapshot(self, snapshot) -> ClaimClusteringResult:
        """Cluster only claims admitted by a revalidated evaluation snapshot."""
        from .snapshot import EvaluationSnapshot

        validated = EvaluationSnapshot.validate_boundary(snapshot)
        result = self.cluster(validated.verified_claims, validated.sources)
        result = result.model_copy(
            update={
                "analysis_id": validated.analysis_id,
                "snapshot_id": validated.snapshot_id,
                "product_identity": validated.product_identity,
                "registry_id": validated.registry_id,
                "registry_revision": validated.registry_revision,
                "input_snapshot_digest": validated.snapshot_id,
                "input_claim_manifest": validated.claim_manifest,
                "provenance_manifest": validated.registry_manifest,
            }
        )
        return result.model_copy(
            update={"content_digest": result.expected_content_digest()}
        )

    @staticmethod
    def validate_snapshot_result(
        snapshot, result: ClaimClusteringResult
    ) -> ClaimClusteringResult:
        """Reject forged or stale cluster artifacts at the next boundary."""
        try:
            validated_result = ClaimClusteringResult.model_validate(
                result.model_dump(mode="python", warnings=False)
            )
        except (AttributeError, TypeError, ValueError, ValidationError) as error:
            raise SourceMetadataError("invalid cluster result schema") from error
        expected_lineage = (
            snapshot.analysis_id,
            snapshot.snapshot_id,
            snapshot.product_identity,
            snapshot.registry_id,
            snapshot.registry_revision,
            snapshot.snapshot_id,
            snapshot.claim_manifest,
            snapshot.registry_manifest,
        )
        actual_lineage = (
            validated_result.analysis_id,
            validated_result.snapshot_id,
            validated_result.product_identity,
            validated_result.registry_id,
            validated_result.registry_revision,
            validated_result.input_snapshot_digest,
            validated_result.input_claim_manifest,
            validated_result.provenance_manifest,
        )
        if actual_lineage != expected_lineage:
            raise SourceMetadataError("cluster lineage does not match its snapshot")
        if (
            validated_result.content_digest
            != validated_result.expected_content_digest()
        ):
            raise SourceMetadataError("cluster content digest mismatch")
        expected_claims = Counter(
            canonical_digest(claim) for claim in snapshot.verified_claims
        )
        actual_claims = Counter(
            canonical_digest(member.claim)
            for cluster in validated_result.clusters
            for member in cluster.members
        )
        if actual_claims != expected_claims:
            raise SourceMetadataError(
                "clusters do not cover the verified claim manifest"
            )
        source_by_id = SemanticClaimClusterer._source_lookup(snapshot.sources)
        confirmed_registry_groups = {
            source.independence_group_id
            for source in source_by_id.values()
            if source.independence_state.value == "confirmed"
        }
        unknown_registry_groups = {
            source.independence_group_id
            for source in source_by_id.values()
            if source.independence_state.value == "unknown"
        }
        member_ids = [
            member.claim_id
            for cluster in validated_result.clusters
            for member in cluster.members
        ]
        expected_ids = {
            f"C{index:03d}" for index in range(1, len(member_ids) + 1)
        }
        if len(member_ids) != len(set(member_ids)) or set(member_ids) != expected_ids:
            raise SourceMetadataError("cluster member IDs are not canonical")
        for index, cluster in enumerate(validated_result.clusters, start=1):
            if cluster.cluster_id != f"CL{index:03d}":
                raise SourceMetadataError("cluster IDs are not canonical")
            SemanticClaimClusterer._validate_cluster_aggregate(
                cluster,
                source_by_id,
                confirmed_registry_groups,
                unknown_registry_groups,
            )
        return validated_result

    @staticmethod
    def _validate_cluster_aggregate(
        cluster: ClaimCluster,
        source_by_id: dict[str, FilteredSource],
        confirmed_registry_groups: set[str],
        unknown_registry_groups: set[str],
    ) -> None:
        source_ids = list(dict.fromkeys(m.claim.source_id for m in cluster.members))
        group_ids = list(dict.fromkeys(m.independence_group_id for m in cluster.members))
        confirmed_groups = [
            group for group in group_ids if group in confirmed_registry_groups
        ]
        unknown_groups = [
            group
            for group in group_ids
            if group in unknown_registry_groups
            and group not in confirmed_registry_groups
        ]
        domains = list(
            dict.fromkeys(source_by_id[source_id].domain for source_id in source_ids)
        )
        severities = [m.claim.severity for m in cluster.members]
        usage_periods = sorted(
            {
                member.claim.usage_period_months
                for member in cluster.members
                if member.claim.usage_period_months is not None
            }
        )
        for member in cluster.members:
            normalized_aspect = ASPECT_ALIASES.get(
                member.claim.aspect, member.claim.aspect
            )
            source = source_by_id.get(member.claim.source_id)
            expected_embedding_key = sha256(
                f"{normalized_aspect} | {member.claim.claim}".encode("utf-8")
            ).hexdigest()
            if (
                source is None
                or normalized_aspect != cluster.aspect
                or member.claim.sentiment is not cluster.sentiment
                or member.independence_group_id != source.independence_group_id
                or member.independence_state is not source.independence_state
                or member.embedding_key != expected_embedding_key
            ):
                raise SourceMetadataError(
                    f"cluster member provenance mismatch: {cluster.cluster_id}"
                )
        if (
            source_ids != cluster.source_ids
            or cluster.source_count != len(source_ids)
            or group_ids != cluster.independence_group_ids
            or confirmed_groups
            != list(cluster.confirmed_independence_group_ids or ())
            or unknown_groups
            != list(cluster.unknown_independence_group_ids or ())
            or cluster.independent_source_count != len(confirmed_groups)
            or domains != cluster.domains
            or cluster.domain_count != len(domains)
            or abs(cluster.average_severity - sum(severities) / len(severities)) > 1e-9
            or cluster.max_severity != max(severities)
            or usage_periods != cluster.usage_period_months
            or cluster.canonical_claim
            not in {member.claim.claim for member in cluster.members}
        ):
            raise SourceMetadataError(f"cluster aggregate mismatch: {cluster.cluster_id}")


    @staticmethod
    def _source_lookup(sources: Iterable[FilteredSource]) -> dict[str, FilteredSource]:
        lookup: dict[str, FilteredSource] = {}
        for source in sources:
            if source.source_key in lookup:
                raise SourceMetadataError(f"duplicate source metadata for {source.source_key}")
            lookup[source.source_key] = source
        return lookup

    def _records_with_embeddings(
        self, claims: Sequence[ExtractedClaim]
    ) -> list[_ClaimRecord]:
        pending: list[tuple[int, ExtractedClaim, str, str, str]] = []
        missing_texts: list[str] = []
        seen_missing: set[str] = set()

        for index, claim in enumerate(claims, start=1):
            aspect = ASPECT_ALIASES.get(claim.aspect, claim.aspect)
            embedding_text = f"{aspect} | {claim.claim}"
            embedding_key = sha256(embedding_text.encode("utf-8")).hexdigest()
            pending.append((index, claim, aspect, embedding_text, embedding_key))
            if embedding_text not in self._embedding_cache and embedding_text not in seen_missing:
                missing_texts.append(embedding_text)
                seen_missing.add(embedding_text)

        if missing_texts:
            vectors = self._provider.embed(missing_texts)
            if len(vectors) != len(missing_texts):
                raise EmbeddingValidationError(
                    "embedding count must match unique embedding input count"
                )
            for text, vector in zip(missing_texts, vectors):
                normalized = normalize_vector(vector)
                self._validate_dimension(normalized)
                self._embedding_cache[text] = normalized

        records = [
            _ClaimRecord(
                index=index,
                claim_id=f"C{index:03d}",
                claim=claim,
                aspect=aspect,
                embedding_text=embedding_text,
                embedding_key=embedding_key,
                vector=self._embedding_cache[embedding_text],
            )
            for index, claim, aspect, embedding_text, embedding_key in pending
        ]
        for record in records:
            self._validate_dimension(record.vector)
        return records

    def _validate_dimension(self, vector: Sequence[float]) -> None:
        if self._embedding_dimension is None:
            self._embedding_dimension = len(vector)
        elif len(vector) != self._embedding_dimension:
            raise EmbeddingValidationError("embedding dimensions must match")

    def _complete_link_clusters(
        self, records: list[_ClaimRecord]
    ) -> list[list[_ClaimRecord]]:
        clusters: list[list[_ClaimRecord]] = []
        for record in records:
            for cluster in clusters:
                if all(
                    cosine_similarity(record.vector, member.vector) + 1e-12
                    >= self._policy.similarity_threshold
                    for member in cluster
                ):
                    cluster.append(record)
                    break
            else:
                clusters.append([record])
        return clusters

    def _build_cluster(
        self,
        cluster_index: int,
        records: list[_ClaimRecord],
        source_by_id: dict[str, FilteredSource],
    ) -> ClaimCluster:
        representative = max(
            records,
            key=lambda candidate: (
                sum(
                    cosine_similarity(candidate.vector, other.vector)
                    for other in records
                ),
                -candidate.index,
            ),
        )
        source_ids = list(dict.fromkeys(record.claim.source_id for record in records))
        source_metadata = [source_by_id[source_id] for source_id in source_ids]
        independence_groups = list(
            dict.fromkeys(source.independence_group_id for source in source_metadata)
        )
        confirmed_registry_groups = {
            source.independence_group_id
            for source in source_by_id.values()
            if source.independence_state.value == "confirmed"
        }
        confirmed_groups = [
            group for group in independence_groups
            if group in confirmed_registry_groups
        ]
        unknown_registry_groups = {
            source.independence_group_id
            for source in source_by_id.values()
            if source.independence_state.value == "unknown"
        }
        unknown_groups = [
            group
            for group in independence_groups
            if group in unknown_registry_groups
            and group not in confirmed_registry_groups
        ]
        domains = list(dict.fromkeys(source.domain for source in source_metadata))
        severities = [record.claim.severity for record in records]
        usage_periods = sorted(
            {
                record.claim.usage_period_months
                for record in records
                if record.claim.usage_period_months is not None
            }
        )

        return ClaimCluster(
            cluster_id=f"CL{cluster_index:03d}",
            canonical_claim=representative.claim.claim,
            aspect=representative.aspect,
            sentiment=representative.claim.sentiment,
            members=[
                ClusterMember(
                    claim_id=record.claim_id,
                    claim=record.claim,
                    embedding_key=record.embedding_key,
                    independence_group_id=source_by_id[
                        record.claim.source_id
                    ].independence_group_id,
                    independence_state=source_by_id[
                        record.claim.source_id
                    ].independence_state,
                )
                for record in records
            ],
            source_ids=source_ids,
            source_count=len(source_ids),
            independence_group_ids=independence_groups,
            confirmed_independence_group_ids=confirmed_groups,
            unknown_independence_group_ids=unknown_groups,
            independent_source_count=len(confirmed_groups),
            domains=domains,
            domain_count=len(domains),
            average_severity=sum(severities) / len(severities),
            max_severity=max(severities),
            usage_period_months=usage_periods,
        )
