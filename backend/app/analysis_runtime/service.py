"""Thin synchronous composition of existing ProofPick public services."""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from uuid import UUID, uuid4

from app.claim_clustering import (
    ClaimClusteringResult,
    EmbeddingProviderError,
    EmbeddingValidationError,
    EvaluationSnapshot,
    SemanticClaimClusterer,
    SnapshotContractError,
    SourceMetadataError,
)
from app.claim_extraction import (
    ClaimGroundingValidator,
    ExtractionFailureCode,
    GroundingState,
    StructuredClaimExtractor,
)
from app.confidence import ConfidenceInputError, ConfidenceResult, EvidenceConfidenceEngine
from app.decision import DecisionInputError, PurchaseDecisionEngine, PurchaseDecisionResult
from app.evidence_processing import DeterministicEvidenceProcessor, EvidenceDocument
from app.models import AnalysisStatus
from app.product_resolution.deterministic import DeterministicProductResolver
from app.product_resolution.exceptions import ProductResolutionError
from app.product_resolution.models import ProductResolution
from app.query_generation.deterministic import DeterministicQueryGenerator
from app.search.exceptions import SearchProviderError
from app.source_filtering import (
    DeterministicSourceFilter,
    FilteredSource,
    SourceIdentityRegistry,
)

from .counter_evidence import CounterEvidenceQueryGenerator
from .exceptions import (
    AnalysisInputError,
    AnalysisIntegrityError,
    AnalysisProviderUnavailableError,
)
from .models import (
    AnalysisClaimSummary,
    AnalysisEvidenceReference,
    AnalysisResponse,
    AnalysisSourceSummary,
)
from .providers import AnalysisRuntimeProviders


logger = logging.getLogger("uvicorn.error.proofpick.analysis")


@dataclass(frozen=True)
class _Evaluation:
    snapshot: EvaluationSnapshot
    sources: tuple[FilteredSource, ...]
    documents: tuple[EvidenceDocument, ...]
    clusters: ClaimClusteringResult
    confidence: ConfidenceResult
    decision: PurchaseDecisionResult


class AnalysisRuntimeService:
    """Execute one bounded analysis plus at most one counter-evidence pass."""

    def __init__(self, providers: AnalysisRuntimeProviders) -> None:
        self._providers = providers
        self._resolver = DeterministicProductResolver()
        self._query_generator = DeterministicQueryGenerator()
        self._counter_query_generator = CounterEvidenceQueryGenerator()
        self._evidence_processor = DeterministicEvidenceProcessor()

    @classmethod
    def from_env(cls) -> "AnalysisRuntimeService":
        return cls(AnalysisRuntimeProviders.from_env())

    def analyze(self, query: str) -> AnalysisResponse:
        started_at = monotonic()
        search_query_count = 0

        def record_search_attempt() -> None:
            nonlocal search_query_count
            search_query_count += 1

        product = self._resolve_product(query)
        analysis_id = str(uuid4())
        registry = SourceIdentityRegistry(analysis_id=analysis_id)
        source_filter = DeterministicSourceFilter(registry=registry)
        query_plan = self._query_generator.generate(product)
        initial_queries = tuple(item.text for item in query_plan.queries)

        try:
            initial_results = self._search(
                initial_queries, on_attempt=record_search_attempt
            )
        except SearchProviderError as error:
            raise AnalysisProviderUnavailableError(
                "search provider is unavailable"
            ) from error
        source_filter.filter(initial_results)
        initial = self._evaluate_final_set(analysis_id, product, registry)

        counter_plan = self._counter_query_generator.generate(
            product_identity=product.canonical_name or "unresolved-product",
            decision=initial.decision,
            clusters=initial.clusters,
            initial_queries=initial_queries,
        )
        if not counter_plan.attempted:
            response = self._response(
                UUID(analysis_id), product, initial, initial,
                attempted=False, completed=False, queries=(),
                counter_source_keys=frozenset(),
            )
            return self._log_completion(
                response, query_count=search_query_count, started_at=started_at
            )

        initial_identity_urls = frozenset(
            url
            for source in initial.sources
            for url in (source.normalized_url, *source.url_aliases)
        )
        try:
            counter_results = self._search(
                counter_plan.queries, on_attempt=record_search_attempt
            )
        except SearchProviderError:
            response = self._response(
                UUID(analysis_id), product, initial, initial,
                attempted=True, completed=False, queries=counter_plan.queries,
                counter_source_keys=frozenset(),
            )
            return self._log_completion(
                response,
                query_count=search_query_count,
                started_at=started_at,
            )

        source_filter.filter(counter_results)
        final = self._evaluate_final_set(analysis_id, product, registry)
        counter_source_keys = frozenset(
            source.source_key
            for source in final.sources
            if not initial_identity_urls.intersection(
                {source.normalized_url, *source.url_aliases}
            )
        )
        response = self._response(
            UUID(analysis_id), product, initial, final,
            attempted=True, completed=True, queries=counter_plan.queries,
            counter_source_keys=counter_source_keys,
        )
        return self._log_completion(
            response,
            query_count=search_query_count,
            started_at=started_at,
        )

    @staticmethod
    def _log_completion(
        response: AnalysisResponse,
        *,
        query_count: int,
        started_at: float,
    ) -> AnalysisResponse:
        logger.info(
            "analysis_complete request_id=%s query_count=%d source_count=%d "
            "decision=%s counter_attempted=%s counter_completed=%s duration_ms=%d",
            response.analysis_id,
            query_count,
            len(response.sources),
            response.decision.value,
            response.counter_evidence_attempted,
            response.counter_evidence_completed,
            round((monotonic() - started_at) * 1000),
        )
        return response

    def _search(
        self,
        queries: tuple[str, ...],
        *,
        on_attempt: Callable[[], None],
    ):
        results = []
        for query in queries:
            on_attempt()
            results.extend(
                self._providers.search.search(
                    query,
                    max_results=5,
                    include_raw_content=True,
                )
            )
        return results

    def _evaluate_final_set(
        self,
        analysis_id: str,
        product: ProductResolution,
        registry: SourceIdentityRegistry,
    ) -> _Evaluation:
        sources = list(registry.retained_sources())
        documents = self._evidence_processor.process_all(sources)
        extractor = StructuredClaimExtractor(
            self._providers.claim_extraction,
            grounding_validator=ClaimGroundingValidator(
                product,
                verification_provider=self._providers.claim_verification,
            ),
        )
        extraction = extractor.extract(documents)
        if any(
            failure.code
            in {
                ExtractionFailureCode.PROVIDER_ERROR,
                ExtractionFailureCode.MALFORMED_OUTPUT,
            }
            for failure in extraction.failures
        ):
            raise AnalysisProviderUnavailableError(
                "claim extraction provider did not return valid structured output"
            )
        verified_assessments = [
            assessment
            for assessment in extraction.grounding_assessments
            if assessment.state is GroundingState.VERIFIED
        ]

        try:
            snapshot = EvaluationSnapshot.create(
                analysis_id=analysis_id,
                product=product,
                registry=registry,
                sources=sources,
                evidence_documents=documents,
                grounding_assessments=verified_assessments,
            )
            clusterer = SemanticClaimClusterer(self._providers.embeddings)
            clusters = clusterer.cluster_snapshot(snapshot)
            confidence_engine = EvidenceConfidenceEngine()
            confidence = confidence_engine.evaluate_snapshot(snapshot, clusters)
            decision = PurchaseDecisionEngine(
                confidence_engine=confidence_engine
            ).evaluate_snapshot(snapshot, confidence, clusters)
        except EmbeddingProviderError as error:
            raise AnalysisProviderUnavailableError(
                "embedding provider is unavailable"
            ) from error
        except (
            EmbeddingValidationError,
            SnapshotContractError,
            SourceMetadataError,
            ConfidenceInputError,
            DecisionInputError,
        ) as error:
            raise AnalysisIntegrityError(
                "analysis artifacts failed integrity validation"
            ) from error

        return _Evaluation(
            snapshot=snapshot,
            sources=tuple(sources),
            documents=tuple(documents),
            clusters=clusters,
            confidence=confidence,
            decision=decision,
        )

    def _resolve_product(self, query: str) -> ProductResolution:
        try:
            product = self._resolver.resolve(query)
        except ProductResolutionError as error:
            raise AnalysisInputError("invalid product query") from error
        if product.ambiguous or not product.canonical_name:
            raise AnalysisInputError(
                "query must resolve to one supported product identity"
            )
        return product

    @staticmethod
    def _response(
        analysis_id: UUID,
        product: ProductResolution,
        initial: _Evaluation,
        final: _Evaluation,
        *,
        attempted: bool,
        completed: bool,
        queries: tuple[str, ...],
        counter_source_keys: frozenset[str],
    ) -> AnalysisResponse:
        source_by_id = {source.source_key: source for source in final.sources}
        document_by_id = {
            document.source_key: document for document in final.documents
        }
        claim_summaries = []
        for cluster in final.clusters.clusters:
            evidence = [
                AnalysisEvidenceReference(
                    source_id=member.claim.source_id,
                    source_url=source_by_id[member.claim.source_id].normalized_url,
                    fragment=member.claim.evidence_fragment,
                )
                for member in cluster.members
            ]
            claim_summaries.append(
                AnalysisClaimSummary(
                    cluster_id=cluster.cluster_id,
                    canonical_claim=cluster.canonical_claim,
                    aspect=cluster.aspect,
                    sentiment=cluster.sentiment,
                    max_severity=cluster.max_severity,
                    independent_source_count=cluster.independent_source_count,
                    evidence=evidence,
                )
            )
        source_summaries = [
            AnalysisRuntimeService._source_summary(source, document_by_id)
            for source in final.sources
        ]
        counter_sources = [
            summary
            for source, summary in zip(final.sources, source_summaries)
            if source.source_key in counter_source_keys
        ]
        return AnalysisResponse(
            analysis_id=analysis_id,
            status=AnalysisStatus.COMPLETE,
            product=product.canonical_name or "unresolved-product",
            initial_decision=initial.decision.decision,
            decision=final.decision.decision,
            confidence=final.confidence.overall_score,
            confidence_level=final.confidence.confidence_level,
            reasons=final.decision.reasons,
            blocking_issues=final.decision.blocking_issues,
            unresolved_risks=final.decision.unresolved_risks,
            counter_evidence_attempted=attempted,
            counter_evidence_completed=completed,
            counter_evidence_queries=list(queries),
            counter_evidence_source_count=len(counter_sources),
            counter_evidence_sources=counter_sources,
            decision_changed=(
                initial.decision.decision is not final.decision.decision
            ),
            claims=claim_summaries,
            sources=source_summaries,
        )

    @staticmethod
    def _source_summary(
        source: FilteredSource,
        document_by_id: dict[str, EvidenceDocument],
    ) -> AnalysisSourceSummary:
        return AnalysisSourceSummary(
            source_id=source.source_key,
            url=source.normalized_url,
            domain=source.domain,
            title=(
                document_by_id[source.source_key].title
                if source.source_key in document_by_id
                else source.title
            ),
            independence_group_id=source.independence_group_id,
        )
