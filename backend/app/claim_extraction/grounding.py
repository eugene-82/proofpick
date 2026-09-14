"""Deterministic conservative source and claim grounding checks."""

import re
from collections.abc import Sequence

from app.evidence_processing.models import EvidenceDocument
from app.models import ClaimSentiment
from app.product_resolution.models import ProductResolution

from .exceptions import ClaimGroundingError
from .models import (
    ClaimExtractionPayload,
    ExtractedClaim,
    GroundingAssessment,
    GroundingReasonCode,
    GroundingState,
)


WORD_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?。！？])\s+|\n+")
NEGATION_PATTERN = re.compile(
    r"\b(?:not|never|no|without|isn['’]?t|wasn['’]?t|didn['’]?t|doesn['’]?t)\b|"
    r"(?:아니|않|없)",
    re.IGNORECASE,
)
NON_EXPERIENCE_PATTERN = re.compile(
    r"\b(?:i|we)\s+(?:have\s+)?never\s+(?:used|owned|tested)\b|"
    r"(?:사용|이용|써)해?\s*본\s*적(?:이)?\s*없",
    re.IGNORECASE,
)
THIRD_PARTY_PATTERN = re.compile(
    r"\baccording to\s+(?:someone|others?|users?)\b|"
    r"\b(?:someone|others?|users?)\s+(?:says?|said|reports?|claims?)\b|"
    r"\b(?:says?|said|reported|claimed)\s+(?:that\s+)?the\b|"
    r"(?:전해|들었다|말한다|주장한다)",
    re.IGNORECASE,
)
SPECULATION_PATTERN = re.compile(
    r"\b(?:might|may|could|possibly|probably|perhaps|seems?)\b|(?:아마|추측|가능성)",
    re.IGNORECASE,
)
NEGATIVE_SIGNAL_PATTERN = re.compile(
    r"\b(?:dead|fail(?:ed|ure|s)?|broken|fire|overheat(?:ed|ing)?|problem|issue|"
    r"drain(?:ed|s|ing)?|disconnect(?:ed|s|ing)?|only)\b|"
    r"(?:고장|불량|발화|과열|문제|끊|닳|나쁘)",
    re.IGNORECASE,
)
POSITIVE_SIGNAL_PATTERN = re.compile(
    r"\b(?:great|good|reliable|works?|lasts?|excellent|satisfied)\b|"
    r"(?:좋|만족|안정|잘\s*된다)",
    re.IGNORECASE,
)
ENGLISH_MONTH_PATTERNS = (
    re.compile(
        r"\b(?:used?|using|owned?|tested?)\s+(?:it\s+|this\s+product\s+)?"
        r"(?:for\s+)?(?<![\d.])(\d+)\s*months?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bafter\s+(?<![\d.])(\d+)\s*months?\s+(?:of\s+)?"
        r"(?:use|usage|ownership)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"(?<![\d.])(\d+)\s*months?\s+(?:of\s+)?(?:use|usage|ownership)\b",
        re.IGNORECASE,
    ),
)
ENGLISH_YEAR_PATTERNS = tuple(
    re.compile(pattern.pattern.replace("months?", "years?"), re.IGNORECASE)
    for pattern in ENGLISH_MONTH_PATTERNS
)
KOREAN_MONTH_PATTERN = re.compile(
    r"(?<![\d.])(\d+)\s*개월(?:간|째)?\s*(?:사용|이용|써|썼)",
    re.IGNORECASE,
)
KOREAN_YEAR_PATTERN = re.compile(
    r"(?<![\d.])(\d+)\s*년(?:간|째)?\s*(?:사용|이용|써|썼)",
    re.IGNORECASE,
)
STOPWORDS = frozenset(
    {"a", "an", "and", "are", "for", "i", "is", "it", "of", "the", "this", "to", "was"}
)


class ClaimGroundingValidator:
    """Only VERIFIED claims may enter clustering, confidence, and decisions."""

    def __init__(self, target_product: ProductResolution | None = None) -> None:
        self._target_product = target_product

    def validate(
        self,
        payload: ClaimExtractionPayload,
        documents: Sequence[EvidenceDocument],
    ) -> ClaimExtractionPayload:
        validated, _ = self.validate_with_assessments(payload, documents)
        return validated

    def validate_with_assessments(
        self,
        payload: ClaimExtractionPayload,
        documents: Sequence[EvidenceDocument],
    ) -> tuple[ClaimExtractionPayload, list[GroundingAssessment]]:
        document_by_id = {document.source_key: document for document in documents}
        source_order = {document.source_key: index for index, document in enumerate(documents)}
        assessments = [self._assess(claim, document_by_id) for claim in payload.claims]
        verified = [
            (index, assessment.claim)
            for index, assessment in enumerate(assessments)
            if assessment.state is GroundingState.VERIFIED
        ]
        if payload.claims and not verified:
            first = assessments[0]
            raise ClaimGroundingError(first.detail, assessments)
        ordered_claims = [
            claim
            for _, claim in sorted(
                verified,
                key=lambda item: (source_order[item[1].source_id], item[0]),
            )
        ]
        return ClaimExtractionPayload(claims=ordered_claims), assessments

    def _assess(
        self,
        claim: ExtractedClaim,
        document_by_id: dict[str, EvidenceDocument],
    ) -> GroundingAssessment:
        document = document_by_id.get(claim.source_id)
        if document is None:
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.SOURCE_MISMATCH,
                f"claim references source_id {claim.source_id} outside its batch",
            )

        fragment = self._normalize_for_match(claim.evidence_fragment)
        source_text = self._normalize_for_match(document.text)
        if fragment not in source_text:
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.FRAGMENT_NOT_FOUND,
                f"evidence_fragment for {claim.source_id} is not present in source text",
            )

        context = self._context_for_fragment(document.text, claim.evidence_fragment)
        identity_state = self._identity_mismatch(context)
        if identity_state is not None:
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.PRODUCT_IDENTITY_MISMATCH,
                identity_state,
            )
        if NON_EXPERIENCE_PATTERN.search(context):
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.NON_EXPERIENCE,
                f"{claim.source_id} explicitly states no direct product experience",
            )
        if THIRD_PARTY_PATTERN.search(context):
            return self._assessment(
                claim,
                GroundingState.UNCERTAIN,
                GroundingReasonCode.THIRD_PARTY_REPORT,
                f"{claim.source_id} evidence is attributed to a third party",
            )
        if SPECULATION_PATTERN.search(context):
            return self._assessment(
                claim,
                GroundingState.UNCERTAIN,
                GroundingReasonCode.SPECULATION,
                f"{claim.source_id} evidence is explicitly speculative",
            )

        claim_negated = bool(NEGATION_PATTERN.search(claim.claim))
        context_negated = bool(NEGATION_PATTERN.search(context))
        if claim_negated != context_negated:
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.NEGATION_MISMATCH,
                f"claim polarity reverses negation in {claim.source_id}",
            )

        fragment_tokens = self._content_tokens(claim.evidence_fragment)
        if len(fragment_tokens) < 2:
            return self._assessment(
                claim,
                GroundingState.UNCERTAIN,
                GroundingReasonCode.TINY_FRAGMENT,
                f"evidence_fragment for {claim.source_id} lacks meaningful context",
            )

        if self._polarity_conflicts(claim, context):
            return self._assessment(
                claim,
                GroundingState.UNCERTAIN,
                GroundingReasonCode.POLARITY_MISMATCH,
                f"claim sentiment is not safely supported by {claim.source_id} context",
            )
        if not self._claim_supported(claim.claim, context):
            return self._assessment(
                claim,
                GroundingState.UNCERTAIN,
                GroundingReasonCode.CLAIM_NOT_SUPPORTED,
                f"claim meaning is not sufficiently represented in {claim.source_id} context",
            )
        if not self._usage_period_supported(claim, context):
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.USAGE_PERIOD_MISMATCH,
                f"usage_period_months for {claim.source_id} is not explicit usage duration",
            )
        return self._assessment(
            claim,
            GroundingState.VERIFIED,
            GroundingReasonCode.VERIFIED,
            f"claim is grounded in {claim.source_id}",
        )

    def _identity_mismatch(self, source_text: str) -> str | None:
        target = self._target_product
        if target is None or target.ambiguous or target.canonical_name is None:
            return None
        normalized = self._normalize_for_match(source_text)
        if target.product_name == "AirPods Pro" and target.generation:
            mentions = set(re.findall(r"airpods\s+pro\s+([123])(?:st|nd|rd)?", normalized))
            expected = {"1st generation": "1", "2nd generation": "2", "3rd generation": "3"}[
                target.generation
            ]
            if mentions and expected not in mentions:
                return f"source explicitly refers to another AirPods Pro generation: {sorted(mentions)}"
        return None

    @staticmethod
    def _context_for_fragment(source_text: str, fragment: str) -> str:
        normalized_fragment = ClaimGroundingValidator._normalize_for_match(fragment)
        for sentence in SENTENCE_SPLIT_PATTERN.split(source_text):
            if normalized_fragment in ClaimGroundingValidator._normalize_for_match(sentence):
                return sentence.strip()
        return source_text

    @staticmethod
    def _content_tokens(text: str) -> set[str]:
        return {
            token
            for token in WORD_PATTERN.findall(text.casefold())
            if token not in STOPWORDS
        }

    @classmethod
    def _claim_supported(cls, claim_text: str, context: str) -> bool:
        normalized_claim = cls._normalize_for_match(claim_text)
        normalized_context = cls._normalize_for_match(context)
        if normalized_claim in normalized_context:
            return True
        claim_tokens = cls._content_tokens(claim_text)
        context_tokens = cls._content_tokens(context)
        if not claim_tokens:
            return False
        return len(claim_tokens & context_tokens) / len(claim_tokens) >= 0.60

    @staticmethod
    def _polarity_conflicts(claim: ExtractedClaim, context: str) -> bool:
        has_negative = bool(NEGATIVE_SIGNAL_PATTERN.search(context))
        has_positive = bool(POSITIVE_SIGNAL_PATTERN.search(context))
        if claim.sentiment is ClaimSentiment.POSITIVE:
            return has_negative
        if claim.sentiment is ClaimSentiment.NEGATIVE:
            return has_positive and not has_negative
        return False

    @staticmethod
    def _usage_period_supported(claim: ExtractedClaim, context: str) -> bool:
        if claim.usage_period_months is None:
            return True
        explicit_months: set[int] = set()
        for pattern in ENGLISH_MONTH_PATTERNS:
            explicit_months.update(int(value) for value in pattern.findall(context))
        for pattern in ENGLISH_YEAR_PATTERNS:
            explicit_months.update(12 * int(value) for value in pattern.findall(context))
        explicit_months.update(int(value) for value in KOREAN_MONTH_PATTERN.findall(context))
        explicit_months.update(12 * int(value) for value in KOREAN_YEAR_PATTERN.findall(context))
        return claim.usage_period_months in explicit_months

    @staticmethod
    def _assessment(
        claim: ExtractedClaim,
        state: GroundingState,
        reason_code: GroundingReasonCode,
        detail: str,
    ) -> GroundingAssessment:
        return GroundingAssessment(
            claim=claim,
            state=state,
            reason_code=reason_code,
            detail=detail,
        )

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        return " ".join(text.casefold().split())
