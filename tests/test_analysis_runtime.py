from collections.abc import Sequence

from fastapi.testclient import TestClient

from app.analysis_runtime import (
    AnalysisRuntimeProviders,
    AnalysisRuntimeService,
)
from app.claim_clustering.base import EmbeddingProvider
from app.claim_clustering.openai_provider import OpenAIEmbeddingProvider
from app.claim_extraction import (
    ClaimExtractionProvider,
    ClaimVerificationProvider,
    EmbeddedClaimVerificationProvider,
    GroundingState,
    OpenAIClaimExtractionProvider,
)
from app.claim_extraction.models import ClaimVerificationVerdict, ExtractedClaim
from app.evidence_processing.models import EvidenceDocument
from app.main import app, get_analysis_runtime_service
from app.search.base import SearchProvider
from app.search.models import SearchResult
from app.search.tavily import TavilySearchProvider


POSITIVE_OBSERVATIONS = (
    "After eight months of daily commuting, the earbuds battery remained reliable and lasted through each workday.",
    "During eight months of office use, I consistently finished the day with dependable battery power.",
    "I owned these earbuds for eight months, and their battery continued working reliably on long walks.",
    "Across eight months of regular travel, the battery stayed dependable without an unexpected shutdown.",
)

NEGATIVE_OBSERVATIONS = (
    "After eight months of daily commuting, the earbuds battery failed completely and stopped powering the device.",
    "During eight months of office use, my battery failed completely and required an unexpected replacement.",
    "I owned these earbuds for eight months before the battery failed completely during a long walk.",
    "Across eight months of regular travel, the battery failed completely and would no longer accept a charge.",
)


class FixtureSearchProvider(SearchProvider):
    def __init__(self, observations: Sequence[str]) -> None:
        self._results = [
            SearchResult(
                title=f"Independent review {index}",
                url=f"https://review-{index}.example.com/airpods-pro-2",
                snippet=text,
                raw_content=text,
            )
            for index, text in enumerate(observations, start=1)
        ]
        self.calls: list[tuple[str, int, bool]] = []

    def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        include_raw_content: bool = False,
    ) -> list[SearchResult]:
        self.calls.append((query, max_results, include_raw_content))
        return list(self._results) if len(self.calls) == 1 else []


class FixtureClaimProvider(ClaimExtractionProvider):
    def __init__(self, *, negative: bool = False, uncertain: bool = False) -> None:
        self._negative = negative
        self._status = (
            GroundingState.UNCERTAIN if uncertain else GroundingState.VERIFIED
        )
        self.calls: list[bool] = []

    def extract_batch(
        self,
        documents: Sequence[EvidenceDocument],
        *,
        repair: bool = False,
        target_product_id: str = "unspecified-product",
    ):
        self.calls.append(repair)
        claim_text = (
            "Battery failed completely during long-term use."
            if self._negative
            else "Battery remained reliable during long-term use."
        )
        return {
            "claims": [
                {
                    "source_id": document.source_key,
                    "aspect": "battery",
                    "claim": claim_text,
                    "sentiment": "negative" if self._negative else "positive",
                    "severity": 5 if self._negative else 1,
                    "usage_period_months": 8,
                    "evidence_fragment": document.text,
                    "semantic_relation": {
                        "target_product_id": target_product_id,
                        "subject": "battery",
                        "predicate": (
                            "failed completely"
                            if self._negative
                            else "remained reliable"
                        ),
                        "polarity": "AFFIRMED",
                        "experiencer": None,
                        "experience_type": "DIRECT",
                        "observation_type": "USAGE",
                        "observation_months": 8,
                        "evidence_quote": document.text,
                        "evidence_source_id": document.source_key,
                        "verification_status": self._status.value,
                    },
                }
                for document in documents
            ]
        }


class RecordingVerificationProvider(ClaimVerificationProvider):
    def __init__(self) -> None:
        self._delegate = EmbeddedClaimVerificationProvider()
        self.calls: list[tuple[bool, int]] = []

    def verify_batch(
        self,
        claims: Sequence[ExtractedClaim],
        documents: Sequence[EvidenceDocument],
        *,
        target_product_id: str,
        repair: bool = False,
    ) -> Sequence[ClaimVerificationVerdict]:
        self.calls.append((repair, len(claims)))
        return self._delegate.verify_batch(
            claims,
            documents,
            target_product_id=target_product_id,
            repair=repair,
        )


class FixtureEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


class InvalidEmbeddingProvider(EmbeddingProvider):
    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        return []


def runtime_service(
    observations: Sequence[str],
    *,
    negative: bool = False,
    uncertain: bool = False,
    embeddings: EmbeddingProvider | None = None,
) -> tuple[AnalysisRuntimeService, RecordingVerificationProvider]:
    verifier = RecordingVerificationProvider()
    providers = AnalysisRuntimeProviders(
        search=FixtureSearchProvider(observations),
        claim_extraction=FixtureClaimProvider(
            negative=negative,
            uncertain=uncertain,
        ),
        claim_verification=verifier,
        embeddings=embeddings or FixtureEmbeddingProvider(),
    )
    return AnalysisRuntimeService(providers), verifier


def post_analysis(service: AnalysisRuntimeService):
    app.dependency_overrides[get_analysis_runtime_service] = lambda: service
    try:
        return TestClient(app).post(
            "/api/analyses", json={"query": "AirPods Pro 2"}
        )
    finally:
        app.dependency_overrides.clear()


def test_runtime_endpoint_reaches_normal_buy() -> None:
    service, verifier = runtime_service(POSITIVE_OBSERVATIONS)

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "complete"
    assert body["decision"] == "BUY"
    assert body["confidence"] >= 0.4
    assert len(body["claims"]) == 1
    assert len(body["claims"][0]["evidence"]) == 4
    assert len(body["sources"]) == 4
    assert verifier.calls == [(False, 4)]


def test_runtime_endpoint_reaches_normal_skip() -> None:
    service, verifier = runtime_service(
        NEGATIVE_OBSERVATIONS,
        negative=True,
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "SKIP"
    assert body["blocking_issues"]
    assert body["blocking_issues"][0]["independent_source_count"] == 4
    assert verifier.calls == [(False, 4)]


def test_runtime_endpoint_returns_early_adopter_for_insufficient_evidence() -> None:
    service, _ = runtime_service(POSITIVE_OBSERVATIONS[:1])

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "EARLY_ADOPTER"
    assert "INSUFFICIENT_EVIDENCE" in body["reasons"]


def test_runtime_endpoint_fails_closed_when_provider_configuration_is_missing(
    monkeypatch,
) -> None:
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    app.dependency_overrides.clear()
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    response = client.post(
        "/api/analyses", json={"query": "AirPods Pro 2"}
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": {
            "code": "MODEL_PROVIDER_UNAVAILABLE",
            "message": "A required analysis provider is unavailable.",
        }
    }
    assert "decision" not in response.json()


def test_runtime_provider_bundle_can_be_constructed_from_configuration(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-search-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-model-key")
    monkeypatch.setenv("OPENAI_CLAIM_MODEL", "test-claim-model")
    monkeypatch.setenv("OPENAI_EMBEDDING_MODEL", "test-embedding-model")

    providers = AnalysisRuntimeProviders.from_env()

    assert isinstance(providers.search, TavilySearchProvider)
    assert isinstance(
        providers.claim_extraction, OpenAIClaimExtractionProvider
    )
    assert isinstance(providers.embeddings, OpenAIEmbeddingProvider)
    providers.claim_extraction._client.close()


def test_semantic_uncertainty_is_not_promoted_by_runtime() -> None:
    service, verifier = runtime_service(
        POSITIVE_OBSERVATIONS,
        uncertain=True,
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "EARLY_ADOPTER"
    assert body["claims"] == []
    assert verifier.calls == [(False, 4), (True, 4)]


def test_runtime_endpoint_fails_closed_on_integrity_violation() -> None:
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS,
        embeddings=InvalidEmbeddingProvider(),
    )

    response = post_analysis(service)

    assert response.status_code == 500
    assert response.json() == {
        "detail": {
            "code": "ANALYSIS_INTEGRITY_ERROR",
            "message": "The analysis could not be completed safely.",
        }
    }
    assert "decision" not in response.json()


def test_runtime_endpoint_rejects_unresolved_product() -> None:
    service, _ = runtime_service(POSITIVE_OBSERVATIONS)
    app.dependency_overrides[get_analysis_runtime_service] = lambda: service
    try:
        response = TestClient(app).post(
            "/api/analyses", json={"query": "unknown product family"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PRODUCT_IDENTITY_UNRESOLVED"
