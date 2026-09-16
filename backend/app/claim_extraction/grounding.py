"""Deterministic conservative source and claim grounding checks."""

import re
from collections.abc import Sequence

from app.evidence_processing.models import EvidenceDocument
from app.models import ClaimSentiment
from app.product_resolution.models import ProductResolution
from app.reliability import extract_relations, relation_supported

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
    r"\b(?:i|we)\s+(?:have\s+)?(?:never|not)\s+(?:used|owned|tested)\b|"
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
    r"\b(?:great|good|reliable|works?|worked|lasts?|excellent|satisfied)\b|"
    r"(?:좋|만족|안정|잘\s*된다)",
    re.IGNORECASE,
)
EVENT_PATTERNS = (
    (
        "fire",
        re.compile(
            r"\b(?:catch|catches|caught)\s+fire\b|\bfire\b|(?:발화|불이\s*났)",
            re.IGNORECASE,
        ),
    ),
    (
        "failure",
        re.compile(
            r"\b(?:fail(?:ed|s|ure)?|broke|broken|stopped\s+working)\b|(?:고장|작동[^.!?]*(?:않|멈))",
            re.IGNORECASE,
        ),
    ),
    (
        "overheat",
        re.compile(r"\boverheat(?:ed|s|ing)?\b|(?:과열)", re.IGNORECASE),
    ),
    (
        "disconnect",
        re.compile(r"\bdisconnect(?:ed|s|ing)?\b|(?:연결[^.!?]*(?:끊|실패))", re.IGNORECASE),
    ),
    (
        "drain",
        re.compile(r"\bdrain(?:ed|s|ing)?\b|(?:배터리[^.!?]*(?:닳|소모))", re.IGNORECASE),
    ),
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
    {
        "a",
        "an",
        "and",
        "are",
        "for",
        "i",
        "is",
        "it",
        "my",
        "of",
        "our",
        "the",
        "this",
        "to",
        "was",
        "we",
    }
)
SUBJECT_STOPWORDS = STOPWORDS | frozenset(
    {
        "after",
        "also",
        "but",
        "completely",
        "could",
        "did",
        "do",
        "does",
        "eventually",
        "finally",
        "had",
        "has",
        "have",
        "just",
        "may",
        "might",
        "never",
        "not",
        "repeatedly",
        "suddenly",
        "will",
        "would",
    }
)


class ClaimGroundingValidator:
    """Only VERIFIED claim cores may enter clustering and decisions."""

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
            grounded_claim
            for _, grounded_claim in sorted(
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

        if not document.grounding_eligible:
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.UNSAFE_PARTIAL_EVIDENCE,
                f"{claim.source_id} contains only incomplete diagnostic spans",
            )
        decision_text = document.grounding_text or document.text
        fragment = self._normalize_for_match(claim.evidence_fragment)
        source_text = self._normalize_for_match(decision_text)
        if fragment not in source_text:
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.FRAGMENT_NOT_FOUND,
                f"evidence_fragment for {claim.source_id} is not present in source text",
            )

        claim_context, usage_context = self._contexts_for_fragment(
            decision_text, claim.evidence_fragment
        )
        identity_state = self._identity_mismatch(
            claim_context, claim.claim, claim.evidence_fragment
        )
        if identity_state is not None:
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.PRODUCT_IDENTITY_MISMATCH,
                identity_state,
            )
        if NON_EXPERIENCE_PATTERN.search(claim_context):
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.NON_EXPERIENCE,
                f"{claim.source_id} explicitly states no direct product experience",
            )
        if THIRD_PARTY_PATTERN.search(claim_context):
            return self._assessment(
                claim,
                GroundingState.UNCERTAIN,
                GroundingReasonCode.THIRD_PARTY_REPORT,
                f"{claim.source_id} evidence is attributed to a third party",
            )
        if SPECULATION_PATTERN.search(claim_context):
            return self._assessment(
                claim,
                GroundingState.UNCERTAIN,
                GroundingReasonCode.SPECULATION,
                f"{claim.source_id} evidence is explicitly speculative",
            )

        if not extract_relations(claim.claim):
            claim_negated = bool(NEGATION_PATTERN.search(claim.claim))
            context_negated = bool(NEGATION_PATTERN.search(claim_context))
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

        if not self._subject_predicate_supported(
            claim.claim, claim_context, usage_context
        ):
            return self._assessment(
                claim,
                GroundingState.REJECTED,
                GroundingReasonCode.SUBJECT_PREDICATE_MISMATCH,
                f"claim subject or predicate is not supported by {claim.source_id}",
            )
        if self._polarity_conflicts(claim, claim_context):
            return self._assessment(
                claim,
                GroundingState.UNCERTAIN,
                GroundingReasonCode.POLARITY_MISMATCH,
                f"claim sentiment is not safely supported by {claim.source_id} context",
            )
        if not self._claim_supported(claim.claim, claim_context):
            return self._assessment(
                claim,
                GroundingState.UNCERTAIN,
                GroundingReasonCode.CLAIM_NOT_SUPPORTED,
                f"claim meaning is not sufficiently represented in {claim.source_id} context",
            )

        grounded_claim = claim
        metadata_issues: list[GroundingReasonCode] = []
        if not self._usage_period_supported(claim, usage_context):
            grounded_claim = claim.model_copy(update={"usage_period_months": None})
            metadata_issues.append(GroundingReasonCode.USAGE_PERIOD_DROPPED)
        detail = f"claim core is grounded in {claim.source_id}"
        if metadata_issues:
            detail += "; unsupported usage_period_months was removed"
        return self._assessment(
            grounded_claim,
            GroundingState.VERIFIED,
            GroundingReasonCode.VERIFIED,
            detail,
            metadata_issues=metadata_issues,
        )

    def _identity_mismatch(
        self,
        context: str,
        claim_text: str,
        fragment: str,
    ) -> str | None:
        target = self._target_product
        if target is None or target.ambiguous or target.canonical_name is None:
            return None
        if target.product_name != "AirPods Pro" or not target.generation:
            return None

        expected = {"1st generation": "1", "2nd generation": "2", "3rd generation": "3"}[
            target.generation
        ]
        generation_pattern = r"airpods\s+pro\s+([123])(?:st|nd|rd)?"
        for label, scope in (("claim", claim_text), ("fragment", fragment), ("context", context)):
            mentions = set(re.findall(generation_pattern, self._normalize_for_match(scope)))
            if mentions and mentions != {expected}:
                return (
                    f"{label} mixes or refers to another AirPods Pro generation: "
                    f"{sorted(mentions)}"
                )
        return None

    @staticmethod
    def _contexts_for_fragment(source_text: str, fragment: str) -> tuple[str, str]:
        sentences = [
            sentence.strip()
            for sentence in SENTENCE_SPLIT_PATTERN.split(source_text)
            if sentence.strip()
        ]
        if not sentences:
            return source_text, source_text
        normalized_fragment = ClaimGroundingValidator._normalize_for_match(fragment)
        matching_index: int | None = None
        for index, sentence in enumerate(sentences):
            if normalized_fragment in ClaimGroundingValidator._normalize_for_match(sentence):
                matching_index = index
                break
        if matching_index is None:
            if normalized_fragment in ClaimGroundingValidator._normalize_for_match(source_text):
                return fragment, fragment
            fragment_tokens = ClaimGroundingValidator._content_tokens(fragment)
            matching_index = max(
                range(len(sentences)),
                key=lambda index: len(
                    fragment_tokens
                    & ClaimGroundingValidator._content_tokens(sentences[index])
                ),
            )
        claim_context = sentences[matching_index]
        start = max(0, matching_index - 1)
        usage_context = " ".join(sentences[start : matching_index + 1])
        return claim_context, usage_context

    @staticmethod
    def _subject_predicate_supported(
        claim_text: str,
        context: str,
        antecedent_context: str,
    ) -> bool:
        return relation_supported(
            claim_text,
            context,
            antecedent=antecedent_context,
        )
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
        claim_tokens = [
            token
            for token in WORD_PATTERN.findall(claim_text.casefold())
            if token not in STOPWORDS
        ]
        context_tokens = [
            token
            for token in WORD_PATTERN.findall(context.casefold())
            if token not in STOPWORDS
        ]
        if not claim_tokens:
            return False
        overlap = len(set(claim_tokens) & set(context_tokens)) / len(set(claim_tokens))
        if overlap < 0.60:
            return False
        position = 0
        matched = 0
        for token in claim_tokens:
            try:
                position = context_tokens.index(token, position) + 1
            except ValueError:
                continue
            matched += 1
        return matched / len(claim_tokens) >= 0.60

    @staticmethod
    def _polarity_conflicts(claim: ExtractedClaim, context: str) -> bool:
        negative_matches = list(NEGATIVE_SIGNAL_PATTERN.finditer(context))
        unnegated_negative = any(
            not ClaimGroundingValidator._negated_at(context, match.start())
            for match in negative_matches
        )
        negated_negative = any(
            ClaimGroundingValidator._negated_at(context, match.start())
            for match in negative_matches
        )
        has_positive = bool(POSITIVE_SIGNAL_PATTERN.search(context))
        if claim.sentiment is ClaimSentiment.POSITIVE:
            return unnegated_negative
        if claim.sentiment is ClaimSentiment.NEGATIVE:
            return has_positive or (negated_negative and not unnegated_negative)
        return False

    @staticmethod
    def _negated_at(text: str, position: int) -> bool:
        prefix = text[max(0, position - 40) : position]
        return bool(NEGATION_PATTERN.search(prefix))

    @staticmethod
    def _usage_period_supported(claim: ExtractedClaim, context: str) -> bool:
        if claim.usage_period_months is None:
            return True
        explicit_months: set[int] = set()
        for pattern in ENGLISH_MONTH_PATTERNS:
            for match in pattern.finditer(context):
                if not ClaimGroundingValidator._negated_at(context, match.start()):
                    explicit_months.add(int(match.group(1)))
        for pattern in ENGLISH_YEAR_PATTERNS:
            for match in pattern.finditer(context):
                if not ClaimGroundingValidator._negated_at(context, match.start()):
                    explicit_months.add(12 * int(match.group(1)))
        explicit_months.update(int(value) for value in KOREAN_MONTH_PATTERN.findall(context))
        explicit_months.update(12 * int(value) for value in KOREAN_YEAR_PATTERN.findall(context))
        return claim.usage_period_months in explicit_months

    @staticmethod
    def _assessment(
        claim: ExtractedClaim,
        state: GroundingState,
        reason_code: GroundingReasonCode,
        detail: str,
        *,
        metadata_issues: list[GroundingReasonCode] | None = None,
    ) -> GroundingAssessment:
        return GroundingAssessment(
            claim=claim,
            state=state,
            reason_code=reason_code,
            detail=detail,
            metadata_issues=metadata_issues or [],
        )

    @staticmethod
    def _normalize_for_match(text: str) -> str:
        return " ".join(text.casefold().split())
