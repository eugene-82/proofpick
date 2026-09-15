from collections.abc import Sequence

import pytest

from app.claim_clustering import (
    ClaimClusteringPolicy,
    EmbeddingProvider,
    EmbeddingProviderTimeoutError,
    EmbeddingValidationError,
    SemanticClaimClusterer,
    SourceMetadataError,
)
from app.claim_extraction import ExtractedClaim
from app.source_filtering import FilteredSource, IndependenceState, SourceType


class FakeEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        vectors: dict[str, list[float]] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.vectors = vectors or {}
        self.error = error
        self.calls: list[list[str]] = []

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        if self.error is not None:
            raise self.error
        return [self.vectors[text] for text in texts]


def extracted_claim(
    source_id: str,
    text: str,
    *,
    aspect: str = "battery",
    sentiment: str = "negative",
    severity: int = 3,
    usage_period_months: int | None = None,
) -> ExtractedClaim:
    return ExtractedClaim(
        source_id=source_id,
        aspect=aspect,
        claim=text,
        sentiment=sentiment,
        severity=severity,
        usage_period_months=usage_period_months,
        evidence_fragment=text,
    )


def filtered_source(
    source_id: str,
    *,
    domain: str | None = None,
    independence_group_id: str | None = None,
) -> FilteredSource:
    resolved_domain = domain or f"{source_id.casefold()}.example"
    return FilteredSource(
        source_key=source_id,
        original_url=f"https://{resolved_domain}/{source_id}",
        normalized_url=f"https://{resolved_domain}/{source_id}",
        domain=resolved_domain,
        title=f"Review {source_id}",
        snippet="Evidence.",
        source_type=SourceType.WEB,
        independence_group_id=independence_group_id or f"IG{source_id[1:]}",
        independence_state=IndependenceState.CONFIRMED,
    )


def embedding_text(claim: ExtractedClaim, normalized_aspect: str | None = None) -> str:
    return f"{normalized_aspect or claim.aspect} | {claim.claim}"


def test_semantically_similar_claims_form_one_cluster() -> None:
    claims = [
        extracted_claim("S001", "배터리가 빨리 닳는다"),
        extracted_claim("S002", "장기 사용 후 배터리 지속시간이 줄었다"),
    ]
    provider = FakeEmbeddingProvider(
        {
            embedding_text(claims[0]): [1.0, 0.0],
            embedding_text(claims[1]): [0.99, 0.1],
        }
    )

    result = SemanticClaimClusterer(provider).cluster(
        claims, [filtered_source("S001"), filtered_source("S002")]
    )

    assert len(result.clusters) == 1
    assert len(result.clusters[0].members) == 2


def test_different_meanings_form_different_clusters() -> None:
    claims = [
        extracted_claim("S001", "Battery drains quickly"),
        extracted_claim("S002", "Battery casing is scratched"),
    ]
    provider = FakeEmbeddingProvider(
        {
            embedding_text(claims[0]): [1.0, 0.0],
            embedding_text(claims[1]): [0.0, 1.0],
        }
    )

    result = SemanticClaimClusterer(provider).cluster(
        claims, [filtered_source("S001"), filtered_source("S002")]
    )

    assert len(result.clusters) == 2


def test_positive_and_negative_claims_never_merge() -> None:
    claims = [
        extracted_claim("S001", "Battery lasts all day", sentiment="positive"),
        extracted_claim("S002", "Battery drains too quickly", sentiment="negative"),
    ]
    provider = FakeEmbeddingProvider(
        {embedding_text(claim): [1.0, 0.0] for claim in claims}
    )

    result = SemanticClaimClusterer(provider).cluster(
        claims, [filtered_source("S001"), filtered_source("S002")]
    )

    assert len(result.clusters) == 2
    assert {cluster.sentiment.value for cluster in result.clusters} == {"positive", "negative"}


def test_different_aspects_do_not_merge_even_with_identical_vectors() -> None:
    claims = [
        extracted_claim("S001", "Battery issue", aspect="battery"),
        extracted_claim("S002", "Noise issue", aspect="noise"),
    ]
    provider = FakeEmbeddingProvider(
        {embedding_text(claim): [1.0, 0.0] for claim in claims}
    )

    result = SemanticClaimClusterer(provider).cluster(
        claims, [filtered_source("S001"), filtered_source("S002")]
    )

    assert len(result.clusters) == 2
    assert [cluster.aspect for cluster in result.clusters] == ["battery", "noise"]


def test_small_aspect_alias_map_allows_compatible_battery_labels() -> None:
    claims = [
        extracted_claim("S001", "Battery drains quickly", aspect="battery"),
        extracted_claim("S002", "Runtime dropped after months", aspect="battery_life"),
    ]
    provider = FakeEmbeddingProvider(
        {
            embedding_text(claims[0]): [1.0, 0.0],
            embedding_text(claims[1], "battery"): [0.99, 0.1],
        }
    )

    result = SemanticClaimClusterer(provider).cluster(
        claims, [filtered_source("S001"), filtered_source("S002")]
    )

    assert len(result.clusters) == 1
    assert result.clusters[0].aspect == "battery"


def test_provenance_counts_unique_sources_groups_and_domains() -> None:
    claims = [
        extracted_claim("S001", "Battery drains quickly"),
        extracted_claim("S001", "Battery drains quickly"),
        extracted_claim("S002", "Battery capacity declined"),
        extracted_claim("S003", "Battery runtime declined"),
    ]
    provider = FakeEmbeddingProvider(
        {embedding_text(claim): [1.0, 0.0] for claim in claims}
    )
    sources = [
        filtered_source("S001", domain="reddit.com", independence_group_id="IG001"),
        filtered_source("S002", domain="forum.example", independence_group_id="IG002"),
        filtered_source("S003", domain="forum.example", independence_group_id="IG002"),
    ]

    cluster = SemanticClaimClusterer(provider).cluster(claims, sources).clusters[0]

    assert cluster.source_ids == ["S002", "S001", "S003"]
    assert cluster.source_count == 3
    assert cluster.independence_group_ids == ["IG002", "IG001"]
    assert cluster.independent_source_count == 2
    assert cluster.domains == ["forum.example", "reddit.com"]
    assert cluster.domain_count == 2
    assert len(cluster.members) == 4


def test_cluster_and_member_ordering_is_stable() -> None:
    claims = [
        extracted_claim("S001", "First battery claim"),
        extracted_claim("S002", "Noise claim", aspect="noise"),
        extracted_claim("S003", "Second battery claim"),
    ]
    provider = FakeEmbeddingProvider(
        {
            embedding_text(claims[0]): [1.0, 0.0],
            embedding_text(claims[1]): [0.0, 1.0],
            embedding_text(claims[2]): [0.99, 0.1],
        }
    )
    sources = [filtered_source(f"S{index:03d}") for index in range(1, 4)]

    first = SemanticClaimClusterer(provider).cluster(claims, sources)
    second = SemanticClaimClusterer(provider).cluster(claims, sources)

    assert first == second
    assert [cluster.cluster_id for cluster in first.clusters] == ["CL001", "CL002"]
    assert [member.claim_id for member in first.clusters[0].members] == ["C001", "C002"]


def test_similarity_threshold_boundary_is_inclusive() -> None:
    claims = [
        extracted_claim("S001", "Claim one"),
        extracted_claim("S002", "Claim two"),
    ]
    provider = FakeEmbeddingProvider(
        {
            embedding_text(claims[0]): [1.0, 0.0],
            embedding_text(claims[1]): [0.8, 0.6],
        }
    )
    policy = ClaimClusteringPolicy(similarity_threshold=0.8)

    result = SemanticClaimClusterer(provider, policy).cluster(
        claims, [filtered_source("S001"), filtered_source("S002")]
    )

    assert len(result.clusters) == 1


@pytest.mark.parametrize(
    "vectors",
    [
        [[0.0, 0.0]],
        [[]],
        [[float("nan"), 1.0]],
    ],
)
def test_zero_or_invalid_embedding_is_rejected(vectors: list[list[float]]) -> None:
    claim = extracted_claim("S001", "Claim")
    provider = FakeEmbeddingProvider({embedding_text(claim): vectors[0]})

    with pytest.raises(EmbeddingValidationError):
        SemanticClaimClusterer(provider).cluster([claim], [filtered_source("S001")])


def test_dimension_mismatch_is_rejected() -> None:
    claims = [
        extracted_claim("S001", "Claim one"),
        extracted_claim("S002", "Claim two"),
    ]
    provider = FakeEmbeddingProvider(
        {
            embedding_text(claims[0]): [1.0, 0.0],
            embedding_text(claims[1]): [1.0, 0.0, 0.0],
        }
    )

    with pytest.raises(EmbeddingValidationError):
        SemanticClaimClusterer(provider).cluster(
            claims, [filtered_source("S001"), filtered_source("S002")]
        )


def test_provider_timeout_propagates_without_partial_clusters() -> None:
    claim = extracted_claim("S001", "Claim")
    provider = FakeEmbeddingProvider(error=EmbeddingProviderTimeoutError("timed out"))

    with pytest.raises(EmbeddingProviderTimeoutError):
        SemanticClaimClusterer(provider).cluster([claim], [filtered_source("S001")])


def test_empty_claim_list_does_not_call_provider() -> None:
    provider = FakeEmbeddingProvider()

    result = SemanticClaimClusterer(provider).cluster([], [])

    assert result.clusters == []
    assert provider.calls == []


def test_single_claim_preserves_identity_and_provenance() -> None:
    claim = extracted_claim("S001", "A single useful claim", severity=4)
    provider = FakeEmbeddingProvider({embedding_text(claim): [1.0, 0.0]})

    cluster = SemanticClaimClusterer(provider).cluster(
        [claim], [filtered_source("S001")]
    ).clusters[0]

    assert cluster.canonical_claim == claim.claim
    assert cluster.members[0].claim_id == "C001"
    assert cluster.members[0].claim == claim
    assert len(cluster.members[0].embedding_key) == 64


def test_severity_and_usage_periods_are_aggregated_without_loss() -> None:
    claims = [
        extracted_claim("S001", "First claim", severity=2, usage_period_months=6),
        extracted_claim("S002", "Second claim", severity=4, usage_period_months=12),
        extracted_claim("S003", "Third claim", severity=3, usage_period_months=6),
    ]
    provider = FakeEmbeddingProvider(
        {embedding_text(claim): [1.0, 0.0] for claim in claims}
    )

    cluster = SemanticClaimClusterer(provider).cluster(
        claims, [filtered_source(f"S{index:03d}") for index in range(1, 4)]
    ).clusters[0]

    assert cluster.average_severity == 3
    assert cluster.max_severity == 4
    assert cluster.usage_period_months == [6, 12]


def test_embeddings_are_compact_batched_and_cached_in_memory() -> None:
    claims = [
        extracted_claim("S001", "Battery claim"),
        extracted_claim("S002", "Noise claim", aspect="noise"),
    ]
    provider = FakeEmbeddingProvider(
        {
            embedding_text(claims[0]): [1.0, 0.0],
            embedding_text(claims[1]): [0.0, 1.0],
        }
    )
    clusterer = SemanticClaimClusterer(provider)
    sources = [filtered_source("S001"), filtered_source("S002")]

    clusterer.cluster(claims, sources)
    clusterer.cluster(claims, sources)

    assert provider.calls == [[embedding_text(claims[0]), embedding_text(claims[1])]]
    assert all("https://" not in text for text in provider.calls[0])
    assert all("Evidence." not in text for text in provider.calls[0])


def test_missing_source_metadata_is_rejected_before_embedding() -> None:
    claim = extracted_claim("S001", "Claim")
    provider = FakeEmbeddingProvider()

    with pytest.raises(SourceMetadataError):
        SemanticClaimClusterer(provider).cluster([claim], [])
    assert provider.calls == []
