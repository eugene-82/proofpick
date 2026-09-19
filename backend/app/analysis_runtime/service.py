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
from app.product_catalog import canonicalize_demo_product
from app.product_resolution.deterministic import DeterministicProductResolver
from app.product_resolution.exceptions import ProductResolutionError
from app.product_resolution.models import ProductResolution
from app.product_resolution.search_assisted import SearchAssistedIdentityResolver
from app.query_generation.deterministic import DeterministicQueryGenerator
from app.search.exceptions import SearchProviderError
from app.source_filtering import (
    DeterministicSourceFilter,
    FilteredSource,
    SourceIdentityRegistry,
)

from .counter_evidence import CounterEvidenceQueryGenerator
from .community_evidence import KoreanCommunityQueryGenerator
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
        self._search_identity_resolver = SearchAssistedIdentityResolver()
        self._query_generator = DeterministicQueryGenerator()
        self._community_query_generator = KoreanCommunityQueryGenerator()
        self._counter_query_generator = CounterEvidenceQueryGenerator()
        self._evidence_processor = DeterministicEvidenceProcessor()

    @classmethod
    def from_env(cls) -> "AnalysisRuntimeService":
        return cls(AnalysisRuntimeProviders.from_env())

    def analyze(self, query: str) -> AnalysisResponse:
        started_at = monotonic()
        search_query_count = 0
        canonical_query = canonicalize_demo_product(query)

        def record_search_attempt() -> None:
            nonlocal search_query_count
            search_query_count += 1

        analysis_id = str(uuid4())
        product = self._resolve_product(canonical_query)
        provisional_candidate = None
        probe_results = []
        probe_query: str | None = None
        if product.ambiguous or not product.canonical_name:
            provisional_candidate = (
                self._search_identity_resolver.provisional_candidate(canonical_query)
            )
            if provisional_candidate is None:
                logger.info("product_identity_unresolved stage=initial")
                raise AnalysisInputError(
                    "query must resolve to one supported product identity"
                )
            logger.info(
                "product_identity_provisional stage=candidate model_term_count=%d",
                len(provisional_candidate.model_terms),
            )
            probe_query = provisional_candidate.canonical_name
            try:
                probe_results = self._search(
                    (probe_query,), on_attempt=record_search_attempt
                )
            except SearchProviderError as error:
                raise AnalysisProviderUnavailableError(
                    "search provider is unavailable"
                ) from error
            confirmed = self._search_identity_resolver.confirm(
                provisional_candidate, probe_results
            )
            if confirmed is None:
                logger.info(
                    "product_identity_unresolved stage=search_confirmation_failed"
                )
                raise AnalysisInputError(
                    "search results did not confirm one product identity"
                )
            logger.info("product_identity_confirmed stage=search_confirmation")
            product = confirmed
            probe_results = self._search_identity_resolver.supporting_results(
                provisional_candidate, probe_results
            )
        registry = SourceIdentityRegistry(analysis_id=analysis_id)
        source_filter = DeterministicSourceFilter(registry=registry)
        query_plan = self._query_generator.generate(product)
        planned_queries = tuple(item.text for item in query_plan.queries)
        initial_queries = (
            (probe_query, *planned_queries[1:])
            if probe_query is not None
            else planned_queries
        )

        try:
            remaining_queries = (
                initial_queries[1:] if probe_query is not None else initial_queries
            )
            initial_results = [
                *probe_results,
                *self._search(
                    remaining_queries, on_attempt=record_search_attempt
                ),
            ]
            if provisional_candidate is not None:
                initial_results = self._search_identity_resolver.supporting_results(
                    provisional_candidate, initial_results
                )
        except SearchProviderError as error:
            raise AnalysisProviderUnavailableError(
                "search provider is unavailable"
            ) from error
        source_filter.filter(initial_results)
        initial = self._evaluate_final_set(analysis_id, product, registry)

        community_boost_attempted = False
        community_query_count = 0
        community_source_count = 0
        after_community = initial
        community_plan = self._community_query_generator.generate(
            product_identity=product.canonical_name or "unresolved-product",
            decision=initial.decision.decision,
            previous_queries=initial_queries,
        )
        searched_queries = initial_queries
        if community_plan.attempted:
            community_boost_attempted = True
            initial_source_keys = {
                source.source_key for source in initial.sources
            }
            initial_registry_revision = registry.revision

            def record_community_search_attempt() -> None:
                nonlocal community_query_count
                community_query_count += 1
                record_search_attempt()

            try:
                community_results = self._search(
                    community_plan.queries,
                    on_attempt=record_community_search_attempt,
                )
                if provisional_candidate is not None:
                    community_results = (
                        self._search_identity_resolver.supporting_results(
                            provisional_candidate, community_results
                        )
                    )
            except SearchProviderError:
                logger.warning(
                    "community_boost_incomplete stage=search query_count=%d",
                    community_query_count,
                )
            else:
                source_filter.filter(community_results)
                community_source_count = sum(
                    source.source_key not in initial_source_keys
                    for source in registry.retained_sources()
                )
                if registry.revision != initial_registry_revision:
                    after_community = self._evaluate_final_set(
                        analysis_id, product, registry
                    )
                searched_queries = (*initial_queries, *community_plan.queries)

        counter_plan = self._counter_query_generator.generate(
            product_identity=product.canonical_name or "unresolved-product",
            decision=after_community.decision,
            clusters=after_community.clusters,
            initial_queries=searched_queries,
        )
        if not counter_plan.attempted:
            response = self._response(
                UUID(analysis_id), product, initial, after_community,
                attempted=False, completed=False, queries=(),
                counter_source_keys=frozenset(),
            )
            return self._log_completion(
                response,
                query_count=search_query_count,
                started_at=started_at,
                community_boost_attempted=community_boost_attempted,
                community_query_count=community_query_count,
                community_source_count=community_source_count,
                decision_before_community=initial.decision.decision.value,
                decision_after_community=after_community.decision.decision.value,
            )

        pre_counter_identity_urls = frozenset(
            url
            for source in after_community.sources
            for url in (source.normalized_url, *source.url_aliases)
        )
        try:
            counter_results = self._search(
                counter_plan.queries, on_attempt=record_search_attempt
            )
            if provisional_candidate is not None:
                counter_results = self._search_identity_resolver.supporting_results(
                    provisional_candidate, counter_results
                )
        except SearchProviderError:
            response = self._response(
                UUID(analysis_id), product, initial, after_community,
                attempted=True, completed=False, queries=counter_plan.queries,
                counter_source_keys=frozenset(),
            )
            return self._log_completion(
                response,
                query_count=search_query_count,
                started_at=started_at,
                community_boost_attempted=community_boost_attempted,
                community_query_count=community_query_count,
                community_source_count=community_source_count,
                decision_before_community=initial.decision.decision.value,
                decision_after_community=after_community.decision.decision.value,
            )

        source_filter.filter(counter_results)
        final = self._evaluate_final_set(analysis_id, product, registry)
        counter_source_keys = frozenset(
            source.source_key
            for source in final.sources
            if not pre_counter_identity_urls.intersection(
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
            community_boost_attempted=community_boost_attempted,
            community_query_count=community_query_count,
            community_source_count=community_source_count,
            decision_before_community=initial.decision.decision.value,
            decision_after_community=after_community.decision.decision.value,
        )

    @staticmethod
    def _log_completion(
        response: AnalysisResponse,
        *,
        query_count: int,
        started_at: float,
        community_boost_attempted: bool,
        community_query_count: int,
        community_source_count: int,
        decision_before_community: str,
        decision_after_community: str,
    ) -> AnalysisResponse:
        logger.info(
            "analysis_complete request_id=%s query_count=%d source_count=%d "
            "decision=%s community_boost_attempted=%s "
            "community_query_count=%d community_source_count=%d "
            "decision_before_community=%s decision_after_community=%s "
            "counter_attempted=%s counter_completed=%s duration_ms=%d",
            response.analysis_id,
            query_count,
            len(response.sources),
            response.decision.value,
            community_boost_attempted,
            community_query_count,
            community_source_count,
            decision_before_community,
            decision_after_community,
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
