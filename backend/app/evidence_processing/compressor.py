"""Deterministic extractive compression with polarity and document coverage."""

import re
from dataclasses import dataclass

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


@dataclass(frozen=True)
class CompressionResult:
    text: str
    truncated: bool


class EvidenceCompressor:
    """Use available budget across regions while retaining both risk and counter-evidence."""

    def __init__(self, policy: EvidenceBudgetPolicy) -> None:
        self._policy = policy

    def compress(self, text: str) -> CompressionResult:
        limit = self._policy.max_chars_per_source
        if len(text) <= limit:
            return CompressionResult(text=text, truncated=False)
        units = [part.strip() for part in SENTENCE_SPLIT_PATTERN.split(text) if part.strip()]
        if len(units) <= 1:
            return CompressionResult(self._bounded_single_unit(text, limit), True)

        mandatory = {0, len(units) // 2, len(units) - 1}
        for pattern in (RISK_PATTERN, POSITIVE_PATTERN, USAGE_PATTERN, NEGATION_PATTERN):
            matches = [index for index, unit in enumerate(units) if pattern.search(unit)]
            if matches:
                mandatory.add(matches[0])
                mandatory.add(matches[-1])

        ordered_mandatory = sorted(mandatory)
        mandatory_length = sum(len(units[index]) for index in ordered_mandatory)
        mandatory_length += max(0, len(ordered_mandatory) - 1)
        if mandatory_length > limit:
            quota = max(1, (limit - max(0, len(ordered_mandatory) - 1)) // len(ordered_mandatory))
            sections = []
            for index in ordered_mandatory:
                unit = units[index]
                signal = next(
                    (
                        match
                        for pattern in (RISK_PATTERN, POSITIVE_PATTERN, USAGE_PATTERN, NEGATION_PATTERN)
                        if (match := pattern.search(unit)) is not None
                    ),
                    None,
                )
                if index == len(units) - 1 or (signal and signal.start() > len(unit) // 2):
                    sections.append(self._safe_suffix(unit, quota))
                else:
                    sections.append(self._safe_prefix(unit, quota))
            return CompressionResult(" ".join(sections)[:limit].rstrip(), True)

        selected: set[int] = set()
        used = 0
        separator = 1
        for index in ordered_mandatory:
            unit = units[index]
            needed = len(unit) + (separator if selected else 0)
            selected.add(index)
            used += needed

        # Fill all remaining space in document order. This redistributes budget left
        # unused by short mandatory regions instead of imposing equal section quotas.
        for index, unit in enumerate(units):
            if index in selected:
                continue
            needed = len(unit) + (separator if selected else 0)
            if used + needed <= limit:
                selected.add(index)
                used += needed

        if not selected:
            return CompressionResult(self._bounded_single_unit(text, limit), True)
        result = " ".join(units[index] for index in sorted(selected))
        if len(result) < min(limit // 2, len(text)) and len(units) > 1:
            result = self._prefix_suffix(text, limit)
        return CompressionResult(result[:limit].rstrip(), True)

    @staticmethod
    def _bounded_single_unit(text: str, limit: int) -> str:
        has_early_positive = (
            (match := POSITIVE_PATTERN.search(text)) is not None and match.start() < len(text) // 2
        )
        has_late_risk = (
            (match := RISK_PATTERN.search(text)) is not None and match.start() >= len(text) // 2
        )
        if has_early_positive and has_late_risk:
            return EvidenceCompressor._prefix_suffix(text, limit)
        matches = [
            match for pattern in (RISK_PATTERN, POSITIVE_PATTERN, USAGE_PATTERN, NEGATION_PATTERN)
            if (match := pattern.search(text)) is not None
        ]
        if matches and min(match.start() for match in matches) > len(text) // 2:
            return EvidenceCompressor._safe_suffix(text, limit)
        return EvidenceCompressor._safe_prefix(text, limit)

    @staticmethod
    def _prefix_suffix(text: str, limit: int) -> str:
        if limit <= 1:
            return "…"[:limit]
        left_budget = (limit - 1) // 2
        right_budget = limit - 1 - left_budget
        left = EvidenceCompressor._safe_prefix(text, left_budget)
        right = EvidenceCompressor._safe_suffix(text, right_budget)
        return (left.rstrip("… ") + "…" + right.lstrip("… "))[:limit]

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
        sentence_start = max(text.rfind(".", 0, start), text.rfind("!", 0, start),
                             text.rfind("?", 0, start), text.rfind("\n", 0, start)) + 1
        preceding = text[sentence_start:start]
        negations = list(NEGATION_PATTERN.finditer(preceding))
        if negations:
            start = sentence_start + negations[-1].start()
        else:
            boundary = text.find(" ", start)
            if boundary != -1:
                start = boundary + 1
        return f"…{text[start:].lstrip()}"[-limit:]
