"""Deterministic extractive compression with polarity and document coverage."""

import re
from dataclasses import dataclass

from .models import EvidenceSegment
from .policy import EvidenceBudgetPolicy


RISK_PATTERN = re.compile(
    r"\b(?:fail(?:ed|ure|s)?|broken|defect|issue|problem|overheat(?:ed|ing)?|"
    r"fire|drain(?:ed|s|ing)?|disconnect(?:ed|s|ing)?|regret)\b|"
    r"(?:고장|불량|문제|과열|발화|끊김|끊긴|닳는다|후회)", re.I
)
POSITIVE_PATTERN = re.compile(
    r"\b(?:great|good|excellent|reliable|works?|worked|satisfied|never\s+failed|"
    r"without\s+(?:a\s+)?problem)\b|(?:좋|만족|안정|잘\s*된다)", re.I
)
USAGE_PATTERN = re.compile(
    r"\b(?:used?|using|owned?|tested?|after|months?|years?|long[- ]term)\b|"
    r"(?:사용|이용|개월|년째|장기)", re.I
)
NEGATION_PATTERN = re.compile(
    r"\b(?:not|never|no|without|isn['’]?t|wasn['’]?t|didn['’]?t|doesn['’]?t)\b|"
    r"(?:아니|않|없)", re.I
)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?。！？])\s+|\n+")
SIGNAL_PATTERNS = (NEGATION_PATTERN, RISK_PATTERN, POSITIVE_PATTERN, USAGE_PATTERN)


@dataclass(frozen=True)
class CompressionResult:
    text: str
    truncated: bool
    grounding_text: str | None
    grounding_eligible: bool
    segments: tuple[EvidenceSegment, ...]
    evidence_coverage_limited: bool
    unsafe_partial_risk: bool


class EvidenceCompressor:
    """Use the budget across regions without changing evidence polarity."""

    def __init__(self, policy: EvidenceBudgetPolicy) -> None:
        self._policy = policy

    def compress(self, text: str) -> CompressionResult:
        limit = self._policy.max_chars_per_source
        if len(text) <= limit:
            return CompressionResult(
                text, False, text, True,
                (EvidenceSegment(
                    text=text, complete=True, truncated=False,
                    grounding_eligible=True,
                    original_start=0, original_end=len(text),
                ),),
                False, False,
            )
        units = [
            part.strip()
            for part in SENTENCE_SPLIT_PATTERN.split(text)
            if part.strip()
        ]
        if len(units) <= 1:
            excerpt = self._bounded_single_unit(text, limit)
            return CompressionResult(
                excerpt, True, None, False,
                (EvidenceSegment(
                    text=excerpt, complete=False, truncated=True,
                    grounding_eligible=False,
                ),),
                True, bool(RISK_PATTERN.search(excerpt)),
            )

        mandatory = {0, len(units) // 2, len(units) - 1}
        for pattern in (RISK_PATTERN, POSITIVE_PATTERN, USAGE_PATTERN, NEGATION_PATTERN):
            matches = [index for index, unit in enumerate(units) if pattern.search(unit)]
            if matches:
                mandatory.update((matches[0], matches[-1]))

        ordered_mandatory = sorted(mandatory)
        separator_budget = max(0, len(ordered_mandatory) - 1)
        mandatory_length = sum(len(units[index]) for index in ordered_mandatory)
        if mandatory_length + separator_budget > limit:
            quotas = self._quotas(limit - separator_budget, len(ordered_mandatory))
            sections = [
                self._excerpt_unit(units[index], quota)
                for index, quota in zip(ordered_mandatory, quotas, strict=True)
            ]
            grounding_units = [
                units[index]
                for index, quota in zip(ordered_mandatory, quotas, strict=True)
                if len(units[index]) <= quota
            ]
            grounding_text = " ".join(grounding_units) or None
            segments = tuple(
                EvidenceSegment(
                    text=section,
                    complete=len(units[index]) <= quota,
                    truncated=len(units[index]) > quota,
                    grounding_eligible=len(units[index]) <= quota,
                )
                for index, quota, section in zip(
                    ordered_mandatory, quotas, sections, strict=True
                )
            )
            unsafe_partial_risk = any(
                (not segment.grounding_eligible)
                and bool(RISK_PATTERN.search(segment.text))
                for segment in segments
            )
            return CompressionResult(
                " ".join(sections).rstrip(), True, grounding_text,
                grounding_text is not None, segments, True,
                unsafe_partial_risk,
            )

        selected = set(ordered_mandatory)
        used = mandatory_length + separator_budget
        for index, unit in enumerate(units):
            if index in selected:
                continue
            needed = len(unit) + 1
            if used + needed <= limit:
                selected.add(index)
                used += needed
        result = " ".join(units[index] for index in sorted(selected))
        segments = tuple(
            EvidenceSegment(
                text=units[index], complete=True, truncated=False,
                grounding_eligible=True,
            )
            for index in sorted(selected)
        )
        return CompressionResult(
            result.rstrip(), True, result.rstrip(), True, segments, True, False
        )

    @staticmethod
    def _quotas(total: int, count: int) -> list[int]:
        base, remainder = divmod(max(total, count), count)
        return [base + (1 if index < remainder else 0) for index in range(count)]

    @staticmethod
    def _excerpt_unit(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        matches = [
            match for pattern in SIGNAL_PATTERNS
            if (match := pattern.search(text)) is not None
        ]
        if not matches:
            return EvidenceCompressor._safe_prefix(text, limit)
        signal = min(matches, key=lambda match: match.start())
        start = signal.start()
        end = signal.end()
        is_negation = NEGATION_PATTERN.fullmatch(signal.group()) is not None
        # A negator and its predicate are an atomic proposition.  Prefer that
        # complete phrase over surrounding prose when a quota is tight.
        if is_negation:
            auxiliary = re.search(
                r"\b(?:did|does|do|is|was|were|are|has|have|had)\s+$",
                text[:start],
                re.I,
            )
            if auxiliary:
                start = auxiliary.start()
            following = re.match(r"\s+[\w'’-]+", text[end:])
            if following:
                end += following.end()
        else:
            preceding = text[max(0, start - 40):start]
            negations = list(NEGATION_PATTERN.finditer(preceding))
            if negations:
                start = max(0, start - 40) + negations[-1].start()
            else:
                preceding_words = list(re.finditer(r"\S+", text[:start]))
                if preceding_words:
                    start = preceding_words[max(0, len(preceding_words) - 2)].start()
        available = max(0, limit - 2)
        atomic_end = end
        if end - start < available:
            end = min(len(text), start + available)
        excerpt = text[start:end].strip()
        boundary = excerpt.rfind(" ")
        if (
            end < len(text)
            and boundary > max(0, len(excerpt) // 2)
            and start + boundary >= atomic_end
        ):
            excerpt = excerpt[:boundary]
        prefix = "…" if start > 0 else ""
        suffix = "…" if end < len(text) else ""
        result = prefix + excerpt + suffix
        return result[:limit]

    @staticmethod
    def _bounded_single_unit(text: str, limit: int) -> str:
        positive = list(POSITIVE_PATTERN.finditer(text))
        risks = list(RISK_PATTERN.finditer(text))
        if positive and risks and positive[0].start() < len(text) // 2 <= risks[-1].start():
            return EvidenceCompressor._prefix_suffix(text, limit)
        matches = [
            match
            for pattern in SIGNAL_PATTERNS
            for match in pattern.finditer(text)
        ]
        if matches:
            important = max(matches, key=lambda match: match.start())
            if important.start() > len(text) // 2:
                return EvidenceCompressor._signal_suffix(text, important.start(), limit)
        return EvidenceCompressor._safe_prefix(text, limit)

    @staticmethod
    def _prefix_suffix(text: str, limit: int) -> str:
        if limit <= 1:
            return "…"[:limit]
        left_budget = (limit - 1) // 2
        right_budget = limit - 1 - left_budget
        left = EvidenceCompressor._safe_prefix(text, left_budget).rstrip("… ")
        right = EvidenceCompressor._safe_suffix(text, right_budget).lstrip("… ")
        return left + "…" + right

    @staticmethod
    def _signal_suffix(text: str, signal_start: int, limit: int) -> str:
        preceding = text[max(0, signal_start - 40):signal_start]
        negations = list(NEGATION_PATTERN.finditer(preceding))
        if negations:
            start = max(0, signal_start - 40) + negations[-1].start()
        else:
            preceding_words = list(re.finditer(r"\S+", text[:signal_start]))
            start = (
                preceding_words[max(0, len(preceding_words) - 2)].start()
                if preceding_words else signal_start
            )
        return EvidenceCompressor._safe_prefix("…" + text[start:].lstrip(), limit)

    @staticmethod
    def _safe_prefix(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        if limit <= 1:
            return "…"[:limit]
        candidate = text[: limit - 1]
        boundary = max(candidate.rfind(" "), candidate.rfind("\n"))
        if boundary > 0:
            candidate = candidate[:boundary]
        return f"{candidate.rstrip()}…"

    @staticmethod
    def _safe_suffix(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        if limit <= 1:
            return "…"[:limit]
        start = len(text) - (limit - 1)
        sentence_start = max(
            text.rfind(".", 0, start),
            text.rfind("!", 0, start),
            text.rfind("?", 0, start),
            text.rfind("\n", 0, start),
        ) + 1
        preceding = text[sentence_start:start]
        negations = list(NEGATION_PATTERN.finditer(preceding))
        if negations:
            start = sentence_start + negations[-1].start()
        else:
            boundary = text.find(" ", start)
            if boundary != -1:
                start = boundary + 1
        suffix = text[start:].lstrip()
        if len(suffix) > limit - 1:
            suffix = EvidenceCompressor._safe_prefix(suffix, limit - 1).rstrip("…")
        return "…" + suffix
