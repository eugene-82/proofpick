import logging
from collections.abc import Sequence
from hashlib import sha256

import pytest
from fastapi.testclient import TestClient

from app.analysis_runtime import (
    AnalysisProviderUnavailableError,
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
from app.confidence import ConfidenceInputError, EvidenceConfidenceEngine
from app.main import app, get_analysis_runtime_service
from app.search.base import SearchProvider
from app.search.exceptions import SearchProviderError
from app.search.models import SearchResult
from app.search.tavily import TavilySearchProvider
from app.source_filtering import SourceType


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
    def __init__(
        self,
        observations: Sequence[str],
        *,
        community_observations: Sequence[str] = (),
        counter_observations: Sequence[str] = (),
        fail_community: bool = False,
        fail_counter: bool = False,
    ) -> None:
        self._initial_results = [
            SearchResult(
                title=f"Independent review {index}",
                url=f"https://review-{index}.example.com/airpods-pro-2",
                snippet=text,
                raw_content=text,
            )
            for index, text in enumerate(observations, start=1)
        ]
        self._counter_results = [
            SearchResult(
                title=f"Counter review {index}",
                url=(
                    "https://counter.example.net/"
                    f"{sha256(text.encode('utf-8')).hexdigest()[:16]}"
                ),
                snippet=text,
                raw_content=text,
            )
            for index, text in enumerate(counter_observations, start=1)
        ]
        community_domains = (
            "gall.dcinside.com",
            "m.fmkorea.com",
            "www.theqoo.net",
            "board.arca.live",
            "bbs.ruliweb.com",
        )
        self._community_results = [
            SearchResult(
                title=f"Community owner review {index}",
                url=(
                    f"https://{community_domains[(index - 1) % len(community_domains)]}"
                    f"/review/{index}"
                ),
                snippet=text,
                raw_content=text,
            )
            for index, text in enumerate(community_observations, start=1)
        ]
        self._community_returned = False
        self._counter_returned = False
        self._fail_community = fail_community
        self._fail_counter = fail_counter
        self.calls: list[tuple[str, int, bool]] = []

    def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        include_raw_content: bool = False,
    ) -> list[SearchResult]:
        self.calls.append((query, max_results, include_raw_content))
        call_number = len(self.calls)
        if call_number == 1:
            return list(self._initial_results)
        if call_number <= 3:
            return []
        if "site:" in query:
            if self._fail_community:
                raise SearchProviderError("community search unavailable")
            if self._community_returned:
                return []
            self._community_returned = True
            return list(self._community_results)
        if not self._counter_returned:
            if self._fail_counter:
                raise SearchProviderError("counter search unavailable")
            self._counter_returned = True
            return list(self._counter_results)
        return []


class FixtureClaimProvider(ClaimExtractionProvider):
    def __init__(self, *, uncertain: bool = False) -> None:
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
        return {
            "claims": [
                {
                    "source_id": document.source_key,
                    "aspect": "battery",
                    "claim": (
                        "Battery failed completely during long-term use."
                        if "failed completely" in document.text.casefold()
                        else "Battery remained reliable during long-term use."
                    ),
                    "sentiment": (
                        "negative"
                        if "failed completely" in document.text.casefold()
                        else "positive"
                    ),
                    "severity": (
                        5
                        if "failed completely" in document.text.casefold()
                        else 1
                    ),
                    "usage_period_months": 8,
                    "evidence_fragment": document.text[:500],
                    "semantic_relation": {
                        "target_product_id": target_product_id,
                        "subject": "battery",
                        "predicate": (
                            "failed completely"
                            if "failed completely" in document.text.casefold()
                            else "remained reliable"
                        ),
                        "polarity": "AFFIRMED",
                        "experiencer": None,
                        "experience_type": "DIRECT",
                        "observation_type": "USAGE",
                        "observation_months": 8,
                        "evidence_quote": document.text[:500],
                        "evidence_source_id": document.source_key,
                        "verification_status": (
                            GroundingState.UNCERTAIN.value
                            if "semantic uncertain" in document.text.casefold()
                            else self._status.value
                        ),
                    },
                }
                for document in documents
                if "irrelevant" not in document.text.casefold()
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


class TrackingAnalysisRuntimeService(AnalysisRuntimeService):
    def __init__(self, providers: AnalysisRuntimeProviders) -> None:
        super().__init__(providers)
        self.evaluations = []

    def _evaluate_final_set(self, analysis_id, product, registry):
        evaluation = super()._evaluate_final_set(
            analysis_id, product, registry
        )
        self.evaluations.append(evaluation)
        return evaluation


def runtime_service(
    observations: Sequence[str],
    *,
    uncertain: bool = False,
    embeddings: EmbeddingProvider | None = None,
    community_observations: Sequence[str] = (),
    counter_observations: Sequence[str] = (),
    fail_community: bool = False,
    fail_counter: bool = False,
    tracking: bool = False,
) -> tuple[AnalysisRuntimeService, RecordingVerificationProvider]:
    verifier = RecordingVerificationProvider()
    providers = AnalysisRuntimeProviders(
        search=FixtureSearchProvider(
            observations,
            community_observations=community_observations,
            counter_observations=counter_observations,
            fail_community=fail_community,
            fail_counter=fail_counter,
        ),
        claim_extraction=FixtureClaimProvider(uncertain=uncertain),
        claim_verification=verifier,
        embeddings=embeddings or FixtureEmbeddingProvider(),
    )
    service_type = (
        TrackingAnalysisRuntimeService if tracking else AnalysisRuntimeService
    )
    return service_type(providers), verifier


def post_analysis(
    service: AnalysisRuntimeService, query: str = "AirPods Pro 2"
):
    app.dependency_overrides[get_analysis_runtime_service] = lambda: service
    try:
        return TestClient(app).post(
            "/api/analyses", json={"query": query}
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
    assert body["initial_decision"] == "BUY"
    assert body["counter_evidence_attempted"] is True
    assert body["counter_evidence_completed"] is True
    assert 1 <= len(body["counter_evidence_queries"]) <= 3
    assert body["counter_evidence_source_count"] == 0
    assert body["decision_changed"] is False
    assert verifier.calls == [(False, 4), (False, 4)]
    search = service._providers.search
    assert isinstance(search, FixtureSearchProvider)
    assert not any("site:" in query for query, _, _ in search.calls)


def test_runtime_success_log_is_bounded_and_contains_demo_metrics(caplog) -> None:
    service, _ = runtime_service(POSITIVE_OBSERVATIONS)

    logger_name = "uvicorn.error.proofpick.analysis"
    with caplog.at_level(logging.INFO, logger=logger_name):
        response = post_analysis(service)

    assert response.status_code == 200
    record = next(
        record
        for record in caplog.records
        if record.name == logger_name
    )
    message = record.getMessage()
    search = service._providers.search
    assert isinstance(search, FixtureSearchProvider)
    assert "analysis_complete request_id=" in message
    assert f"query_count={len(search.calls)}" in message
    assert "source_count=4" in message
    assert "decision=BUY" in message
    assert "counter_attempted=True" in message
    assert "counter_completed=True" in message
    assert "community_boost_attempted=False" in message
    assert "community_query_count=0" in message
    assert "duration_ms=" in message
    assert "AirPods Pro 2" not in message
    assert POSITIVE_OBSERVATIONS[0] not in message


def test_runtime_endpoint_reaches_normal_skip() -> None:
    service, verifier = runtime_service(
        NEGATIVE_OBSERVATIONS,
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "SKIP"
    assert body["blocking_issues"]
    assert body["blocking_issues"][0]["independent_source_count"] == 4
    assert body["initial_decision"] == "SKIP"
    assert body["counter_evidence_attempted"] is True
    assert body["counter_evidence_completed"] is True
    assert "battery no issue long term" in body["counter_evidence_queries"][0]
    assert verifier.calls == [(False, 4), (False, 4)]


def test_runtime_endpoint_returns_early_adopter_for_insufficient_evidence() -> None:
    service, _ = runtime_service(POSITIVE_OBSERVATIONS[:1])

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "EARLY_ADOPTER"
    assert "INSUFFICIENT_EVIDENCE" in body["reasons"]
    assert body["counter_evidence_attempted"] is False
    assert body["counter_evidence_completed"] is False
    assert body["counter_evidence_queries"] == []
    search = service._providers.search
    assert isinstance(search, FixtureSearchProvider)
    community_queries = [
        query for query, _, _ in search.calls if "site:" in query
    ]
    assert len(community_queries) == 3
    assert len(search.calls) == 6


def test_community_boost_can_add_verified_evidence_and_change_decision(
    caplog,
) -> None:
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS[:1],
        community_observations=POSITIVE_OBSERVATIONS[1:],
        tracking=True,
    )

    logger_name = "uvicorn.error.proofpick.analysis"
    with caplog.at_level(logging.INFO, logger=logger_name):
        response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["initial_decision"] == "EARLY_ADOPTER"
    assert body["decision"] == "BUY"
    assert len(body["sources"]) == 4
    assert body["claims"][0]["independent_source_count"] == 4
    assert isinstance(service, TrackingAnalysisRuntimeService)
    community_evaluation = service.evaluations[1]
    community_sources = [
        source
        for source in community_evaluation.sources
        if source.source_type is SourceType.COMMUNITY
    ]
    assert len(community_sources) == 3
    search = service._providers.search
    assert isinstance(search, FixtureSearchProvider)
    assert len([query for query, _, _ in search.calls if "site:" in query]) == 3
    assert len(search.calls) <= 10
    message = next(
        record.getMessage()
        for record in caplog.records
        if record.name == logger_name
        and record.getMessage().startswith("analysis_complete")
    )
    assert "community_boost_attempted=True" in message
    assert "community_query_count=3" in message
    assert "community_source_count=3" in message
    assert "decision_before_community=EARLY_ADOPTER" in message
    assert "decision_after_community=BUY" in message
    assert "site:" not in message


def test_community_search_failure_preserves_initial_early_adopter_without_retry() -> None:
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS[:1],
        fail_community=True,
    )

    response = post_analysis(service)

    assert response.status_code == 200
    assert response.json()["decision"] == "EARLY_ADOPTER"
    search = service._providers.search
    assert isinstance(search, FixtureSearchProvider)
    assert len(search.calls) == 4


def test_community_duplicates_do_not_inflate_independent_support() -> None:
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS[:1],
        community_observations=(
            POSITIVE_OBSERVATIONS[0],
            POSITIVE_OBSERVATIONS[1],
            POSITIVE_OBSERVATIONS[2],
        ),
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert len(body["sources"]) == 3
    assert body["claims"][0]["independent_source_count"] == 3


def test_community_then_counter_stays_within_global_query_budget() -> None:
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS[:1],
        community_observations=NEGATIVE_OBSERVATIONS,
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["initial_decision"] == "EARLY_ADOPTER"
    assert body["decision"] == "SKIP"
    search = service._providers.search
    assert isinstance(search, FixtureSearchProvider)
    assert len(search.calls) == 9
    assert len(search.calls) <= 10


@pytest.mark.parametrize(
    ("observations", "expected_decision"),
    [
        (NEGATIVE_OBSERVATIONS[:3], "BUY_IF"),
        (NEGATIVE_OBSERVATIONS, "SKIP"),
    ],
)
def test_non_early_initial_decisions_do_not_run_community_boost(
    observations: Sequence[str], expected_decision: str
) -> None:
    service, _ = runtime_service(observations)

    response = post_analysis(service)

    assert response.status_code == 200
    assert response.json()["initial_decision"] == expected_decision
    search = service._providers.search
    assert isinstance(search, FixtureSearchProvider)
    assert not any("site:" in query for query, _, _ in search.calls)


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
    monkeypatch.setenv("OPENAI_EXTRACTION_TIMEOUT_SECONDS", "75")

    providers = AnalysisRuntimeProviders.from_env()

    assert isinstance(providers.search, TavilySearchProvider)
    assert isinstance(
        providers.claim_extraction, OpenAIClaimExtractionProvider
    )
    assert providers.claim_extraction._timeout_seconds == 75
    assert isinstance(providers.embeddings, OpenAIEmbeddingProvider)
    providers.claim_extraction._client.close()


def test_runtime_provider_uses_bounded_default_extraction_timeout(
    monkeypatch,
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-search-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-model-key")
    monkeypatch.delenv("OPENAI_EXTRACTION_TIMEOUT_SECONDS", raising=False)

    providers = AnalysisRuntimeProviders.from_env()

    assert providers.claim_extraction._timeout_seconds == 90
    providers.claim_extraction._client.close()


@pytest.mark.parametrize("value", ["0", "inf", "301", "not-a-number"])
def test_runtime_provider_rejects_unbounded_extraction_timeout(
    monkeypatch, value: str
) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "test-search-key")
    monkeypatch.setenv("OPENAI_API_KEY", "test-model-key")
    monkeypatch.setenv("OPENAI_EXTRACTION_TIMEOUT_SECONDS", value)

    with pytest.raises(
        AnalysisProviderUnavailableError, match="configuration is invalid"
    ):
        AnalysisRuntimeProviders.from_env()


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
    assert body["counter_evidence_attempted"] is False
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


class ProvisionalIdentitySearchProvider(SearchProvider):
    def __init__(self, *, confirmed: bool) -> None:
        self.confirmed = confirmed
        self.calls: list[str] = []

    def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        include_raw_content: bool = False,
    ) -> list[SearchResult]:
        self.calls.append(query)
        if len(self.calls) != 1:
            return []
        titles = (
            [
                "Acme ZX-500 long-term review",
                "Acme ZX-500 owner report",
                "Acme ZX-500 durability test",
                "Acme ZX-400 competing model review",
            ]
            if self.confirmed
            else [
                "Acme ZX-500 review",
                "Acme ZX-400 comparison",
                "Acme products guide",
            ]
        )
        return [
            SearchResult(
                title=title,
                url=f"https://identity-{index}.example.com/acme",
                snippet=POSITIVE_OBSERVATIONS[index % len(POSITIVE_OBSERVATIONS)],
                raw_content=POSITIVE_OBSERVATIONS[index % len(POSITIVE_OBSERVATIONS)],
            )
            for index, title in enumerate(titles, start=1)
        ]


def provisional_runtime(
    *, confirmed: bool
) -> tuple[AnalysisRuntimeService, ProvisionalIdentitySearchProvider]:
    search = ProvisionalIdentitySearchProvider(confirmed=confirmed)
    providers = AnalysisRuntimeProviders(
        search=search,
        claim_extraction=FixtureClaimProvider(),
        claim_verification=RecordingVerificationProvider(),
        embeddings=FixtureEmbeddingProvider(),
    )
    return AnalysisRuntimeService(providers), search


def test_search_confirmed_provisional_identity_enters_normal_pipeline() -> None:
    service, search = provisional_runtime(confirmed=True)

    response = post_analysis(service, "Acme ZX-500")

    assert response.status_code == 200
    assert response.json()["product"] == "Acme ZX-500"
    assert len(response.json()["sources"]) == 3
    assert all(
        "ZX-400" not in (source["title"] or "")
        for source in response.json()["sources"]
    )
    assert len(search.calls) <= 6
    assert search.calls[0] == "Acme ZX-500"


def test_unconfirmed_provisional_identity_still_returns_422() -> None:
    service, search = provisional_runtime(confirmed=False)

    response = post_analysis(service, "Acme ZX-500")

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PRODUCT_IDENTITY_UNRESOLVED"
    assert search.calls == ["Acme ZX-500"]


class ProvisionalCommunitySearchProvider(SearchProvider):
    def __init__(self) -> None:
        self.calls: list[str] = []
        self._community_returned = False

    def search(
        self,
        query: str,
        max_results: int = 5,
        *,
        include_raw_content: bool = False,
    ) -> list[SearchResult]:
        self.calls.append(query)
        if len(self.calls) == 1:
            return [
                SearchResult(
                    title=f"Acme ZX-500 owner review {index}",
                    url=f"https://identity-{index}.example.com/acme-zx-500",
                    snippet=POSITIVE_OBSERVATIONS[index - 1],
                    raw_content=POSITIVE_OBSERVATIONS[index - 1],
                )
                for index in range(1, 3)
            ]
        if len(self.calls) <= 3 or "site:" not in query:
            return []
        if self._community_returned:
            return []
        self._community_returned = True
        return [
            SearchResult(
                title="ZX-500 long-term owner review",
                url="https://gall.dcinside.com/board/view/?id=acme&no=1",
                snippet=POSITIVE_OBSERVATIONS[2],
                raw_content=POSITIVE_OBSERVATIONS[2],
            ),
            SearchResult(
                title="Acme ZX-500 durability review",
                url="https://m.fmkorea.com/123456",
                snippet=POSITIVE_OBSERVATIONS[3],
                raw_content=POSITIVE_OBSERVATIONS[3],
            ),
            SearchResult(
                title="Acme ZX-400 competing model review",
                url="https://theqoo.net/review/999",
                snippet=NEGATIVE_OBSERVATIONS[0],
                raw_content=NEGATIVE_OBSERVATIONS[0],
            ),
        ]


def test_provisional_identity_filters_community_results_within_budget() -> None:
    search = ProvisionalCommunitySearchProvider()
    providers = AnalysisRuntimeProviders(
        search=search,
        claim_extraction=FixtureClaimProvider(),
        claim_verification=RecordingVerificationProvider(),
        embeddings=FixtureEmbeddingProvider(),
    )
    service = AnalysisRuntimeService(providers)

    response = post_analysis(service, "Acme ZX-500")

    assert response.status_code == 200
    body = response.json()
    assert body["initial_decision"] == "EARLY_ADOPTER"
    assert body["decision"] == "BUY"
    assert all("ZX-400" not in (source["title"] or "") for source in body["sources"])
    assert len([query for query in search.calls if "site:" in query]) == 3
    assert len(search.calls) <= 10


def test_existing_galaxy_identity_skips_provisional_probe() -> None:
    service, _ = runtime_service(POSITIVE_OBSERVATIONS)
    search = service._providers.search
    assert isinstance(search, FixtureSearchProvider)

    response = post_analysis(service, "Galaxy Buds3 Pro")

    assert response.status_code == 200
    assert response.json()["product"] == "Samsung Galaxy Buds3 Pro"
    assert search.calls[0][0].startswith("Samsung Galaxy Buds3 Pro")


def test_verified_severe_counter_evidence_reaches_existing_skip_rules() -> None:
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS,
        counter_observations=NEGATIVE_OBSERVATIONS,
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["initial_decision"] == "BUY"
    assert body["decision"] == "SKIP"
    assert body["decision_changed"] is True
    assert body["counter_evidence_source_count"] == 4
    assert body["blocking_issues"][0]["independent_source_count"] == 4


def test_weak_positive_counter_evidence_does_not_force_skip_to_buy() -> None:
    service, _ = runtime_service(
        NEGATIVE_OBSERVATIONS,
        counter_observations=POSITIVE_OBSERVATIONS[:1],
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["initial_decision"] == "SKIP"
    assert body["decision"] == "SKIP"
    assert body["decision_changed"] is False
    assert body["counter_evidence_source_count"] == 1


def test_uncertain_counter_evidence_is_not_promoted_to_verified() -> None:
    uncertain = tuple(
        f"{text} Semantic uncertain."
        for text in NEGATIVE_OBSERVATIONS
    )
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS,
        counter_observations=uncertain,
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["initial_decision"] == "BUY"
    assert body["decision"] != "SKIP"
    assert all(
        claim["sentiment"] != "negative" for claim in body["claims"]
    )


def test_unsafe_partial_counter_evidence_cannot_drive_decision() -> None:
    unsafe_risk = (
        "After eight months the battery failed completely "
        + "diagnosticword " * 500
    )
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS,
        counter_observations=(unsafe_risk,),
        tracking=True,
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["initial_decision"] == "BUY"
    assert body["decision"] != "SKIP"
    assert all(
        claim["sentiment"] != "negative" for claim in body["claims"]
    )
    assert isinstance(service, TrackingAnalysisRuntimeService)
    counter_document = next(
        document
        for document in service.evaluations[-1].documents
        if document.domain == "counter.example.net"
    )
    assert counter_document.evidence_coverage_limited is True
    assert not any(
        segment.grounding_eligible for segment in counter_document.segments
    )


def test_exact_counter_copy_does_not_inflate_source_support() -> None:
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS,
        counter_observations=(POSITIVE_OBSERVATIONS[0],),
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["decision"] == "BUY"
    assert body["counter_evidence_source_count"] == 0
    assert len(body["sources"]) == 4
    assert body["claims"][0]["independent_source_count"] == 4


def test_near_copy_counter_source_is_preserved_but_not_independent_support() -> None:
    footer_copy = (
        POSITIVE_OBSERVATIONS[0]
        + " Legal footer navigation privacy contact terms archive."
    )
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS,
        counter_observations=(footer_copy,),
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["counter_evidence_source_count"] == 1
    assert len(body["sources"]) == 5
    assert body["claims"][0]["independent_source_count"] == 4


def test_counter_search_failure_preserves_initial_safe_result() -> None:
    service, verifier = runtime_service(
        POSITIVE_OBSERVATIONS,
        fail_counter=True,
    )

    response = post_analysis(service)

    assert response.status_code == 200
    body = response.json()
    assert body["initial_decision"] == "BUY"
    assert body["decision"] == "BUY"
    assert body["counter_evidence_attempted"] is True
    assert body["counter_evidence_completed"] is False
    assert body["counter_evidence_source_count"] == 0
    assert verifier.calls == [(False, 4)]


def test_final_snapshot_and_derived_lineage_replace_initial_artifacts() -> None:
    service, _ = runtime_service(
        POSITIVE_OBSERVATIONS,
        counter_observations=NEGATIVE_OBSERVATIONS,
        tracking=True,
    )

    response = post_analysis(service)

    assert response.status_code == 200
    assert isinstance(service, TrackingAnalysisRuntimeService)
    assert len(service.evaluations) == 2
    initial, final = service.evaluations
    assert initial.snapshot.snapshot_id != final.snapshot.snapshot_id
    assert final.clusters.input_snapshot_digest == final.snapshot.snapshot_id
    assert final.confidence.input_snapshot_digest == final.snapshot.snapshot_id
    assert final.confidence.input_cluster_digest == final.clusters.content_digest
    with pytest.raises(ConfidenceInputError):
        EvidenceConfidenceEngine().validate_snapshot_result(
            final.snapshot,
            initial.confidence,
            initial.clusters,
        )


def test_final_semantics_converge_for_counter_result_order() -> None:
    forward, _ = runtime_service(
        POSITIVE_OBSERVATIONS,
        counter_observations=NEGATIVE_OBSERVATIONS,
    )
    reverse, _ = runtime_service(
        POSITIVE_OBSERVATIONS,
        counter_observations=tuple(reversed(NEGATIVE_OBSERVATIONS)),
    )

    forward_body = post_analysis(forward).json()
    reverse_body = post_analysis(reverse).json()

    assert forward_body["decision"] == reverse_body["decision"]
    assert forward_body["confidence"] == reverse_body["confidence"]
    assert forward_body["blocking_issues"] == reverse_body["blocking_issues"]
    assert [
        (claim["canonical_claim"], claim["independent_source_count"])
        for claim in forward_body["claims"]
    ] == [
        (claim["canonical_claim"], claim["independent_source_count"])
        for claim in reverse_body["claims"]
    ]
