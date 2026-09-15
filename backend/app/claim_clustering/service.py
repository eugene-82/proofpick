"""Deterministic semantic claim clustering with complete provenance."""

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from hashlib import sha256

from app.claim_extraction.models import ExtractedClaim
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
        """Cluster only claims admitted by a validated evaluation snapshot."""
        result = self.cluster(snapshot.verified_claims, snapshot.sources)
        return result.model_copy(
            update={
                "analysis_id": snapshot.analysis_id,
                "snapshot_id": snapshot.snapshot_id,
                "product_identity": snapshot.product_identity,
                "registry_id": snapshot.registry_id,
                "registry_revision": snapshot.registry_revision,
            }
        )

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
        confirmed_groups = list(
            dict.fromkeys(
                source.independence_group_id
                for source in source_metadata
                if source.independence_state.value == "confirmed"
            )
        )
        unknown_groups = list(
            dict.fromkeys(
                source.independence_group_id
                for source in source_metadata
                if source.independence_state.value == "unknown"
            )
        )
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
