"""Thin synchronous composition of existing ProofPick public services."""

from uuid import UUID, uuid4

from app.claim_clustering import (
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
from app.confidence import ConfidenceInputError, EvidenceConfidenceEngine
from app.decision import DecisionInputError, PurchaseDecisionEngine
from app.evidence_processing import DeterministicEvidenceProcessor
from app.models import AnalysisStatus
from app.product_resolution.deterministic import DeterministicProductResolver
from app.product_resolution.exceptions import ProductResolutionError
from app.query_generation.deterministic import DeterministicQueryGenerator
from app.search.exceptions import SearchProviderError
from app.source_filtering import DeterministicSourceFilter, SourceIdentityRegistry

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


class AnalysisRuntimeService:
    """Execute one bounded analysis without persistence or background jobs."""

    def __init__(self, providers: AnalysisRuntimeProviders) -> None:
        self._providers = providers
        self._resolver = DeterministicProductResolver()
        self._query_generator = DeterministicQueryGenerator()
        self._evidence_processor = DeterministicEvidenceProcessor()

    @classmethod
    def from_env(cls) -> "AnalysisRuntimeService":
        return cls(AnalysisRuntimeProviders.from_env())

    def analyze(self, query: str) -> AnalysisResponse:
        product = self._resolve_product(query)
        analysis_id = str(uuid4())
        registry = SourceIdentityRegistry(analysis_id=analysis_id)
        source_filter = DeterministicSourceFilter(registry=registry)

        try:
            query_plan = self._query_generator.generate(product)
            search_results = [
                result
                for search_query in query_plan.queries
                for result in self._providers.search.search(
                    search_query.text,
                    max_results=5,
                    include_raw_content=True,
                )
            ]
        except SearchProviderError as error:
            raise AnalysisProviderUnavailableError(
                "search provider is unavailable"
            ) from error

        source_filter.filter(search_results)
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

        return self._response(
            UUID(analysis_id), product.canonical_name or "unresolved-product",
            sources, documents, clusters, confidence, decision,
        )

    def _resolve_product(self, query: str):
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
        analysis_id,
        product,
        sources,
        documents,
        clusters,
        confidence,
        decision,
    ) -> AnalysisResponse:
        source_by_id = {source.source_key: source for source in sources}
        document_by_id = {document.source_key: document for document in documents}
        claim_summaries = []
        for cluster in clusters.clusters:
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
            AnalysisSourceSummary(
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
            for source in sources
        ]
        return AnalysisResponse(
            analysis_id=analysis_id,
            status=AnalysisStatus.COMPLETE,
            product=product,
            decision=decision.decision,
            confidence=confidence.overall_score,
            confidence_level=confidence.confidence_level,
            reasons=decision.reasons,
            blocking_issues=decision.blocking_issues,
            unresolved_risks=decision.unresolved_risks,
            claims=claim_summaries,
            sources=source_summaries,
        )
