"""Immutable in-memory contract for one deterministic evaluation snapshot."""

import json
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.claim_extraction.models import (
    ExtractedClaim,
    GroundingAssessment,
    GroundingReasonCode,
    GroundingState,
)
from app.evidence_processing.models import EvidenceDocument
from app.product_resolution.models import ProductResolution
from app.source_filtering.models import (
    FilteredSource,
    IndependenceReasonCode,
)
from app.source_filtering.registry import SourceIdentityRegistry


class SnapshotContractError(ValueError):
    """Inputs cannot safely be combined into one evaluation snapshot."""


class SnapshotClaim(ExtractedClaim):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, frozen=True
    )


class SnapshotGroundingAssessment(GroundingAssessment):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, frozen=True
    )
    claim: SnapshotClaim
    metadata_issues: tuple[GroundingReasonCode, ...] = ()


class SnapshotSource(FilteredSource):
    model_config = ConfigDict(extra="forbid", frozen=True)
    independence_reason_codes: tuple[IndependenceReasonCode, ...] = ()


class SnapshotEvidenceDocument(EvidenceDocument):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True, frozen=True
    )


class EvaluationSnapshot(BaseModel):
    """Self-validating snapshot used by clustering, confidence, and decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    analysis_id: str = Field(min_length=1)
    snapshot_id: str = Field(pattern=r"^snapshot-[0-9a-f]{16}$")
    registry_id: str = Field(pattern=r"^registry-[0-9a-f]{16}$")
    registry_revision: int = Field(ge=0)
    registry_manifest: str = Field(pattern=r"^[0-9a-f]{64}$")
    registry_source_identities: tuple[tuple[str, str], ...]
    product_identity: str = Field(min_length=1)
    sources: tuple[SnapshotSource, ...]
    evidence_documents: tuple[SnapshotEvidenceDocument, ...]
    grounding_assessments: tuple[SnapshotGroundingAssessment, ...]

    @property
    def verified_claims(self) -> tuple[SnapshotClaim, ...]:
        return tuple(item.claim for item in self.grounding_assessments)

    @model_validator(mode="after")
    def validate_runtime_contract(self) -> "EvaluationSnapshot":
        expected_registry_id = self._registry_id(self.analysis_id)
        if self.registry_id != expected_registry_id:
            raise ValueError("registry belongs to another analysis")

        source_ids = [source.source_key for source in self.sources]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("source identity must be unique")
        identities = tuple(
            sorted(
                (source.source_key, source.independence_group_id)
                for source in self.sources
            )
        )
        if identities != tuple(sorted(self.registry_source_identities)):
            raise ValueError("snapshot sources disagree with registry ownership")
        if len(identities) != len(set(identities)):
            raise ValueError("registry source identity must be unique")
        if self.registry_revision < len(identities):
            raise ValueError("registry revision predates snapshot sources")
        expected_manifest = self._registry_manifest(
            self.analysis_id,
            self.registry_id,
            self.registry_revision,
            identities,
        )
        if self.registry_manifest != expected_manifest:
            raise ValueError("registry manifest or revision mismatch")

        document_ids = [document.source_key for document in self.evidence_documents]
        if len(document_ids) != len(set(document_ids)):
            raise ValueError("evidence source identity must be unique")
        if not set(document_ids).issubset(source_ids):
            raise ValueError("evidence documents must use snapshot sources")
        source_groups = {
            source.source_key: source.independence_group_id
            for source in self.sources
        }
        for document in self.evidence_documents:
            if (
                source_groups[document.source_key]
                != document.independence_group_id
            ):
                raise ValueError("evidence document registry identity mismatch")
        for assessment in self.grounding_assessments:
            if (
                assessment.state is not GroundingState.VERIFIED
                or assessment.reason_code is not GroundingReasonCode.VERIFIED
            ):
                raise ValueError(
                    "unverified claim cannot enter downstream evaluation"
                )
            if assessment.claim.source_id not in document_ids:
                raise ValueError("verified claim lacks snapshot evidence")

        expected_snapshot_id = self._snapshot_id(self._digest_payload())
        if self.snapshot_id != expected_snapshot_id:
            raise ValueError("snapshot digest does not match decision inputs")
        return self

    @classmethod
    def create(
        cls,
        *,
        analysis_id: str,
        product: ProductResolution,
        registry: SourceIdentityRegistry,
        sources: list[FilteredSource],
        evidence_documents: list[EvidenceDocument],
        grounding_assessments: list[GroundingAssessment],
    ) -> "EvaluationSnapshot":
        if registry.analysis_id != analysis_id:
            raise SnapshotContractError("registry belongs to another analysis")
        if product.ambiguous or not product.canonical_name:
            raise SnapshotContractError("stable product identity is required")
        for assessment in grounding_assessments:
            if (
                assessment.state is not GroundingState.VERIFIED
                or assessment.reason_code is not GroundingReasonCode.VERIFIED
            ):
                raise SnapshotContractError(
                    "unverified claim cannot enter downstream evaluation"
                )

        source_identities = tuple(
            sorted(
                (source.source_key, source.independence_group_id)
                for source in sources
            )
        )
        registry_identities = tuple(sorted(registry.identities()))
        if source_identities != registry_identities or any(
            not registry.owns_identity(source_key, group_id)
            for source_key, group_id in source_identities
        ):
            raise SnapshotContractError(
                "all sources must belong to the shared registry revision"
            )
        registry_manifest = cls._registry_manifest(
            analysis_id,
            registry.registry_id,
            registry.revision,
            source_identities,
        )
        values: dict[str, Any] = {
            "analysis_id": analysis_id,
            "registry_id": registry.registry_id,
            "registry_revision": registry.revision,
            "registry_manifest": registry_manifest,
            "registry_source_identities": source_identities,
            "product_identity": product.canonical_name,
            "sources": [source.model_dump(mode="python") for source in sources],
            "evidence_documents": [
                document.model_dump(mode="python")
                for document in evidence_documents
            ],
            "grounding_assessments": [
                assessment.model_dump(mode="python")
                for assessment in grounding_assessments
            ],
        }
        # Hash the same normalized field set that runtime validation recomputes.
        normalized = cls._normalize_values(values)
        values["snapshot_id"] = cls._snapshot_id(
            cls._payload_from_values(normalized)
        )
        try:
            return cls.model_validate(values)
        except ValueError as error:
            raise SnapshotContractError(str(error)) from error

    def model_copy(
        self,
        *,
        update: dict[str, Any] | None = None,
        deep: bool = False,
    ) -> "EvaluationSnapshot":
        data = self.model_dump(mode="python")
        if update:
            data.update(update)
        return type(self).model_validate(data)

    def _digest_payload(self) -> dict[str, Any]:
        return self._payload_from_values(
            {
                "analysis_id": self.analysis_id,
                "registry_id": self.registry_id,
                "registry_revision": self.registry_revision,
                "registry_manifest": self.registry_manifest,
                "registry_source_identities": self.registry_source_identities,
                "product_identity": self.product_identity,
                "sources": self.sources,
                "evidence_documents": self.evidence_documents,
                "grounding_assessments": self.grounding_assessments,
            }
        )

    @classmethod
    def _normalize_values(cls, values: dict[str, Any]) -> dict[str, Any]:
        data = dict(values)
        data["sources"] = tuple(
            SnapshotSource.model_validate(item) for item in values["sources"]
        )
        data["evidence_documents"] = tuple(
            SnapshotEvidenceDocument.model_validate(item)
            for item in values["evidence_documents"]
        )
        data["grounding_assessments"] = tuple(
            SnapshotGroundingAssessment.model_validate(item)
            for item in values["grounding_assessments"]
        )
        return data

    @staticmethod
    def _payload_from_values(values: dict[str, Any]) -> dict[str, Any]:
        sources = values["sources"]
        documents = values["evidence_documents"]
        assessments = values["grounding_assessments"]
        return {
            "analysis_id": values["analysis_id"],
            "registry_id": values["registry_id"],
            "registry_revision": values["registry_revision"],
            "registry_manifest": values["registry_manifest"],
            "registry_source_identities": sorted(
                list(item) for item in values["registry_source_identities"]
            ),
            "product_identity": values["product_identity"],
            "sources": sorted([
                {
                    "source_key": source.source_key,
                    "normalized_url": source.normalized_url,
                    "domain": source.domain,
                    "content_hash": source.content_hash,
                    "source_type": source.source_type.value,
                    "independence_group_id": source.independence_group_id,
                    "independence_state": source.independence_state.value,
                }
                for source in sources
            ], key=lambda item: item["source_key"]),
            "evidence": sorted([
                {
                    "source_key": document.source_key,
                    "text": document.text,
                    "content_hash": document.content_hash,
                    "evidence_source": document.evidence_source.value,
                    "evidence_quality": document.evidence_quality.value,
                    "observation_state": document.observation_state.value,
                    "independence_group_id": document.independence_group_id,
                    "independence_state": document.independence_state.value,
                }
                for document in documents
            ], key=lambda item: item["source_key"]),
            "claims": sorted([
                {
                    "source_id": assessment.claim.source_id,
                    "aspect": assessment.claim.aspect,
                    "claim": assessment.claim.claim,
                    "sentiment": assessment.claim.sentiment.value,
                    "severity": assessment.claim.severity,
                    "usage_period_months": assessment.claim.usage_period_months,
                    "evidence_fragment": assessment.claim.evidence_fragment,
                    "grounding_state": assessment.state.value,
                    "grounding_reason": assessment.reason_code.value,
                    "metadata_issues": sorted(
                        issue.value for issue in assessment.metadata_issues
                    ),
                }
                for assessment in assessments
            ], key=lambda item: (
                item["source_id"], item["aspect"], item["claim"]
            )),
        }

    @staticmethod
    def _snapshot_id(payload: dict[str, Any]) -> str:
        digest = sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()[:16]
        return f"snapshot-{digest}"

    @staticmethod
    def _registry_id(analysis_id: str) -> str:
        digest = sha256(analysis_id.encode("utf-8")).hexdigest()[:16]
        return f"registry-{digest}"

    @staticmethod
    def _registry_manifest(
        analysis_id: str,
        registry_id: str,
        revision: int,
        identities: tuple[tuple[str, str], ...],
    ) -> str:
        payload = {
            "analysis_id": analysis_id,
            "registry_id": registry_id,
            "registry_revision": revision,
            "identities": sorted(list(item) for item in identities),
        }
        return sha256(
            json.dumps(
                payload, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
