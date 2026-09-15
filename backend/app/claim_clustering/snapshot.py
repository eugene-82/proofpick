"""Immutable in-memory contract for one deterministic evaluation snapshot."""

import json
from hashlib import sha256

from pydantic import BaseModel, ConfigDict, Field

from app.claim_extraction.models import ExtractedClaim, GroundingAssessment, GroundingState
from app.evidence_processing.models import EvidenceDocument
from app.product_resolution.models import ProductResolution
from app.source_filtering.models import FilteredSource
from app.source_filtering.registry import SourceIdentityRegistry


class SnapshotContractError(ValueError):
    """Inputs cannot safely be combined into one evaluation snapshot."""


class EvaluationSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_id: str = Field(min_length=1)
    snapshot_id: str = Field(pattern=r"^snapshot-[0-9a-f]{16}$")
    registry_id: str = Field(min_length=1)
    registry_revision: int = Field(ge=0)
    product_identity: str = Field(min_length=1)
    sources: list[FilteredSource]
    evidence_documents: list[EvidenceDocument]
    grounding_assessments: list[GroundingAssessment]

    @property
    def verified_claims(self) -> list[ExtractedClaim]:
        return [item.claim for item in self.grounding_assessments]

    @classmethod
    def create(cls, *, analysis_id: str, product: ProductResolution,
               registry: SourceIdentityRegistry, sources: list[FilteredSource],
               evidence_documents: list[EvidenceDocument],
               grounding_assessments: list[GroundingAssessment]) -> "EvaluationSnapshot":
        if registry.analysis_id != analysis_id:
            raise SnapshotContractError("registry belongs to another analysis")
        if product.ambiguous or not product.canonical_name:
            raise SnapshotContractError("stable product identity is required")
        source_ids = [source.source_key for source in sources]
        if len(source_ids) != len(set(source_ids)):
            raise SnapshotContractError("source identity must be unique")
        if any(not registry.owns_source(source_id) for source_id in source_ids):
            raise SnapshotContractError("all sources must belong to the shared registry")
        document_ids = [document.source_key for document in evidence_documents]
        if len(document_ids) != len(set(document_ids)):
            raise SnapshotContractError("evidence source identity must be unique")
        if not set(document_ids).issubset(source_ids):
            raise SnapshotContractError("evidence documents must use snapshot sources")
        for assessment in grounding_assessments:
            if assessment.state is not GroundingState.VERIFIED:
                raise SnapshotContractError("unverified claim cannot enter downstream evaluation")
            if assessment.claim.source_id not in document_ids:
                raise SnapshotContractError("verified claim lacks snapshot evidence")
        payload = {
            "analysis_id": analysis_id,
            "registry_id": registry.registry_id,
            "registry_revision": registry.revision,
            "product_identity": product.canonical_name,
            "sources": sorted(
                [(s.source_key, s.independence_group_id, s.normalized_url, s.content_hash)
                 for s in sources]
            ),
            "claims": sorted(
                [(a.claim.source_id, a.claim.aspect, a.claim.sentiment.value,
                  a.claim.claim, a.claim.evidence_fragment)
                 for a in grounding_assessments]
            ),
        }
        digest = sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:16]
        return cls(
            analysis_id=analysis_id, snapshot_id=f"snapshot-{digest}",
            registry_id=registry.registry_id, registry_revision=registry.revision,
            product_identity=product.canonical_name,
            sources=[source.model_copy(deep=True) for source in sources],
            evidence_documents=[
                document.model_copy(deep=True) for document in evidence_documents
            ],
            grounding_assessments=[
                assessment.model_copy(deep=True) for assessment in grounding_assessments
            ],
        )
