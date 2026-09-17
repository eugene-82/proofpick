"""Bounded deterministic counter-evidence query planning."""

from dataclasses import dataclass

from app.claim_clustering.models import ClaimClusteringResult
from app.decision.models import PurchaseDecisionResult
from app.models import ClaimSentiment, PurchaseDecision


@dataclass(frozen=True)
class CounterEvidencePlan:
    queries: tuple[str, ...]

    @property
    def attempted(self) -> bool:
        return bool(self.queries)


class CounterEvidenceQueryGenerator:
    """Challenge a completed initial decision without semantic re-judgment."""

    max_queries = 3
    global_query_budget = 10

    def generate(
        self,
        *,
        product_identity: str,
        decision: PurchaseDecisionResult,
        clusters: ClaimClusteringResult,
        initial_queries: tuple[str, ...],
    ) -> CounterEvidencePlan:
        if decision.decision is PurchaseDecision.EARLY_ADOPTER:
            return CounterEvidencePlan(queries=())

        aspect = self._decision_aspect(decision, clusters)
        if decision.decision in {
            PurchaseDecision.BUY,
            PurchaseDecision.BUY_IF,
        }:
            candidates = [
                f"{product_identity} problems long term",
                f"{product_identity} failure issue",
            ]
            if aspect is not None:
                candidates.append(f"{product_identity} {aspect} problems")
        else:
            candidates = []
            if aspect is not None:
                candidates.extend(
                    [
                        f"{product_identity} {aspect} no issue long term",
                        f"{product_identity} {aspect} fixed resolved",
                    ]
                )
            candidates.append(f"{product_identity} long term positive")

        remaining_budget = max(
            0, self.global_query_budget - len(initial_queries)
        )
        limit = min(self.max_queries, remaining_budget)
        if limit == 0:
            return CounterEvidencePlan(queries=())
        existing = {self._normalized(query) for query in initial_queries}
        queries: list[str] = []
        for candidate in candidates:
            normalized = self._normalized(candidate)
            if normalized in existing:
                continue
            existing.add(normalized)
            queries.append(candidate)
            if len(queries) == limit:
                break
        return CounterEvidencePlan(queries=tuple(queries))

    @staticmethod
    def _decision_aspect(
        decision: PurchaseDecisionResult,
        clusters: ClaimClusteringResult,
    ) -> str | None:
        if decision.decision is PurchaseDecision.SKIP:
            candidates = [
                (signal.aspect, signal.independent_source_count, signal.max_severity)
                for signal in decision.blocking_issues
            ]
        else:
            candidates = [
                (cluster.aspect, cluster.independent_source_count, cluster.max_severity)
                for cluster in clusters.clusters
                if cluster.sentiment is ClaimSentiment.POSITIVE
            ]
        if not candidates:
            return None
        aspect, _, _ = min(
            candidates,
            key=lambda item: (-item[1], -item[2], item[0]),
        )
        return " ".join(aspect.replace("_", " ").split())

    @staticmethod
    def _normalized(query: str) -> str:
        return " ".join(query.casefold().split())
