"""Deterministic provenance gate around semantic verification."""

import re
from collections.abc import Sequence

from app.evidence_processing.models import EvidenceDocument
from app.product_resolution.models import ProductResolution

from .exceptions import ClaimGroundingError
from .models import (
    ClaimExtractionPayload,
    ClaimVerificationVerdict,
    ExperienceType,
    ExtractedClaim,
    GroundingAssessment,
    GroundingReasonCode,
    GroundingState,
    ObservationType,
    SemanticRelation,
)
from .verification import (
    ClaimVerificationProvider,
    EmbeddedClaimVerificationProvider,
)


OBSERVED_TYPES = frozenset(
    {ObservationType.USAGE, ObservationType.OWNERSHIP, ObservationType.TEST}
)

_GENERATION_VALUES = {
    "1": 1,
    "1st": 1,
    "first": 1,
    "2": 2,
    "2nd": 2,
    "second": 2,
    "3": 3,
    "3rd": 3,
    "third": 3,
}
_NUMBERED_GENERATION = r"1st|2nd|3rd|1|2|3"
_WORD_GENERATION = r"first|second|third"
_ANY_GENERATION = rf"{_NUMBERED_GENERATION}|{_WORD_GENERATION}"



class ClaimGroundingValidator:
    """Admit only candidate-bound VERIFIED semantic relations with valid provenance."""

    def __init__(
        self,
        target_product: ProductResolution | None = None,
        verification_provider: ClaimVerificationProvider | None = None,
    ) -> None:
        self._target_product = target_product
        self._verifier = verification_provider or EmbeddedClaimVerificationProvider()

    @property
    def target_product_id(self) -> str:
        target = self._target_product
        if target is None or target.ambiguous or not target.canonical_name:
            return "unspecified-product"
        return target.canonical_name

    def validate(
        self,
        payload: ClaimExtractionPayload,
        documents: Sequence[EvidenceDocument],
        *,
        repair: bool = False,
    ) -> ClaimExtractionPayload:
        verified, _ = self.validate_with_assessments(payload, documents, repair=repair)
        return verified

    def validate_with_assessments(
        self,
        payload: ClaimExtractionPayload,
        documents: Sequence[EvidenceDocument],
        *,
        repair: bool = False,
    ) -> tuple[ClaimExtractionPayload, list[GroundingAssessment]]:
        document_by_id = {document.source_key: document for document in documents}
        if len(document_by_id) != len(documents):
            raise ValueError("evidence source IDs must be unique")
        source_order = {
            document.source_key: index for index, document in enumerate(documents)
        }
        preflight: dict[int, GroundingAssessment] = {}
        candidates: list[ExtractedClaim] = []
        for index, claim in enumerate(payload.claims):
            failure = self._preflight(claim, document_by_id)
            if failure is not None:
                preflight[index] = failure
            else:
                candidates.append(claim)

        verdicts = list(
            self._verifier.verify_batch(
                candidates,
                documents,
                target_product_id=self.target_product_id,
                repair=repair,
            )
        ) if candidates else []
        assessments: list[GroundingAssessment] = []
        candidate_index = 0
        for index, claim in enumerate(payload.claims):
            if index in preflight:
                assessments.append(preflight[index])
                continue
            verdict = verdicts[candidate_index] if candidate_index < len(verdicts) else None
            candidate_index += 1
            assessments.append(
                self._assess_verdict(claim, document_by_id[claim.source_id], verdict)
            )
        if len(verdicts) != len(candidates):
            assessments = [
                self._assessment(
                    item.claim,
                    GroundingState.REJECTED,
                    GroundingReasonCode.VERIFICATION_BINDING_MISMATCH,
                    "verifier returned an unexpected number of verdicts",
                )
                if item.state is GroundingState.VERIFIED else item
                for item in assessments
            ]
        verified = [
            (index, assessment.claim)
            for index, assessment in enumerate(assessments)
            if assessment.state is GroundingState.VERIFIED
        ]
        if payload.claims and not verified:
            raise ClaimGroundingError(assessments[0].detail, assessments)
        ordered = [
            item
            for _, item in sorted(
                verified, key=lambda pair: (source_order[pair[1].source_id], pair[0])
            )
        ]
        return ClaimExtractionPayload(claims=ordered), assessments

    def _preflight(
        self,
        claim: ExtractedClaim,
        document_by_id: dict[str, EvidenceDocument],
    ) -> GroundingAssessment | None:
        document = document_by_id.get(claim.source_id)
        if document is None:
            return self._assessment(
                claim, GroundingState.REJECTED, GroundingReasonCode.SOURCE_MISMATCH,
                f"claim references source_id {claim.source_id} outside its batch",
            )
        eligible = self._eligible_texts(document)
        if not eligible:
            return self._assessment(
                claim, GroundingState.REJECTED,
                GroundingReasonCode.UNSAFE_PARTIAL_EVIDENCE,
                f"{claim.source_id} has no complete grounding-eligible span",
            )
        fragment = self._normalize(claim.evidence_fragment)
        if not any(fragment in self._normalize(text) for text in eligible):
            reason = (
                GroundingReasonCode.UNSAFE_PARTIAL_EVIDENCE
                if fragment in self._normalize(document.text)
                else GroundingReasonCode.FRAGMENT_NOT_FOUND
            )
            return self._assessment(
                claim, GroundingState.REJECTED, reason,
                f"evidence fragment is not in a complete eligible span of {claim.source_id}",
            )
        conflicting_generations = self._conflicting_generations(claim)
        if conflicting_generations:
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.PRODUCT_IDENTITY_MISMATCH,
                "claim explicitly references a generation that conflicts "
                "with the resolved target product",
            )
        return None

    def _conflicting_generations(self, claim: ExtractedClaim) -> frozenset[int]:
        target = self._target_product
        if target is None or target.generation is None or target.product_name is None:
            return frozenset()
        target_generation = self._generation_value(target.generation)
        if target_generation is None:
            return frozenset()

        relation = claim.semantic_relation
        subject_generations = (
            self._explicit_generations(relation.subject, target.product_name)
            if relation is not None
            else frozenset()
        )
        mentioned_generations = subject_generations or self._explicit_generations(
            claim.evidence_fragment, target.product_name
        )
        if not mentioned_generations or target_generation in mentioned_generations:
            return frozenset()
        return mentioned_generations

    @staticmethod
    def _generation_value(value: str) -> int | None:
        match = re.search(rf"\b(?P<generation>{_ANY_GENERATION})\b", value, re.I)
        if match is None:
            return None
        return _GENERATION_VALUES[match.group("generation").casefold()]

    @staticmethod
    def _explicit_generations(text: str, product_name: str) -> frozenset[int]:
        family = r"\s+".join(re.escape(part) for part in product_name.split())
        patterns = (
            rf"(?<![A-Za-z0-9]){family}\s*\(?\s*"
            rf"(?P<generation>{_NUMBERED_GENERATION})"
            rf"(?:[-\s]+generation)?\s*\)?(?=$|[^A-Za-z0-9])",
            rf"(?<![A-Za-z0-9]){family}\s*\(?\s*"
            rf"(?P<generation>{_WORD_GENERATION})[-\s]+generation"
            rf"\s*\)?(?=$|[^A-Za-z0-9])",
            rf"(?<![A-Za-z0-9])(?P<generation>{_ANY_GENERATION})"
            rf"[-\s]+generation\s+{family}(?=$|[^A-Za-z0-9])",
        )
        return frozenset(
            _GENERATION_VALUES[match.group("generation").casefold()]
            for pattern in patterns
            for match in re.finditer(pattern, text, re.I)
        )

    def _assess_verdict(
        self,
        claim: ExtractedClaim,
        document: EvidenceDocument,
        verdict: ClaimVerificationVerdict | None,
    ) -> GroundingAssessment:
        if verdict is None or verdict.claim != claim:
            return self._assessment(
                claim, GroundingState.REJECTED,
                GroundingReasonCode.VERIFICATION_BINDING_MISMATCH,
                "semantic verdict does not bind to the candidate claim",
            )
        relation = verdict.relation
        if relation is None:
            return self._assessment(
                claim, GroundingState.UNCERTAIN,
                GroundingReasonCode.SEMANTIC_UNCERTAIN,
                "semantic verifier abstained",
            )
        if not self._relation_bound(claim, document, relation, verdict):
            return self._assessment(
                claim, GroundingState.REJECTED,
                GroundingReasonCode.VERIFICATION_BINDING_MISMATCH,
                "semantic verdict disagrees with source, quote, product, or status",
            )
        if verdict.verification_status is GroundingState.REJECTED:
            return self._assessment(
                claim, GroundingState.REJECTED,
                GroundingReasonCode.SEMANTIC_REJECTED, verdict.detail,
                relation=relation,
            )
        if verdict.verification_status is not GroundingState.VERIFIED:
            return self._assessment(
                claim, GroundingState.UNCERTAIN,
                GroundingReasonCode.SEMANTIC_UNCERTAIN, verdict.detail,
                relation=relation,
            )
        if (
            relation.experience_type is not ExperienceType.DIRECT
            or relation.observation_type is ObservationType.HYPOTHETICAL
        ):
            return self._assessment(
                claim, GroundingState.UNCERTAIN,
                GroundingReasonCode.SEMANTIC_UNCERTAIN,
                "decision-driving direct observation was not verified",
                relation=relation,
            )
        grounded = claim.model_copy(update={"semantic_relation": relation})
        metadata_issues: list[GroundingReasonCode] = []
        if claim.usage_period_months is not None and (
            relation.observation_type not in OBSERVED_TYPES
            or relation.observation_months != claim.usage_period_months
        ):
            grounded = grounded.model_copy(update={"usage_period_months": None})
            metadata_issues.append(GroundingReasonCode.USAGE_PERIOD_DROPPED)
        return self._assessment(
            grounded, GroundingState.VERIFIED, GroundingReasonCode.VERIFIED,
            "candidate-bound semantic relation and provenance were verified",
            relation=relation, metadata_issues=metadata_issues,
        )

    def _relation_bound(
        self,
        claim: ExtractedClaim,
        document: EvidenceDocument,
        relation: SemanticRelation,
        verdict: ClaimVerificationVerdict,
    ) -> bool:
        quote = self._normalize(relation.evidence_quote)
        return (
            relation.evidence_source_id == claim.source_id
            and relation.target_product_id == self.target_product_id
            and quote == self._normalize(claim.evidence_fragment)
            and any(
                quote in self._normalize(text)
                for text in self._eligible_texts(document)
            )
            and relation.verification_status is verdict.verification_status
        )

    @staticmethod
    def _eligible_texts(document: EvidenceDocument) -> tuple[str, ...]:
        if document.segments:
            return tuple(
                segment.text for segment in document.segments
                if segment.complete and segment.grounding_eligible
                and not segment.truncated
            )
        if document.grounding_eligible:
            return (document.grounding_text or document.text,)
        return ()

    @staticmethod
    def _normalize(text: str) -> str:
        return " ".join(text.casefold().split())

    @staticmethod
    def _assessment(
        claim: ExtractedClaim,
        state: GroundingState,
        reason: GroundingReasonCode,
        detail: str,
        *,
        relation: SemanticRelation | None = None,
        metadata_issues: list[GroundingReasonCode] | None = None,
    ) -> GroundingAssessment:
        return GroundingAssessment(
            claim=claim, state=state, reason_code=reason, detail=detail,
            metadata_issues=metadata_issues or [], semantic_relation=relation,
        )
