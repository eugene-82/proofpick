"""Deterministic, context-preserving extractive evidence bounding."""

import re
from dataclasses import dataclass

from .policy import EvidenceBudgetPolicy


RISK_PATTERN = re.compile(
    r"\b(?:fail(?:ed|ure|s)?|broken|defect|issue|problem|overheat(?:ed|ing)?|"
    r"fire|drain(?:ed|s|ing)?|disconnect(?:ed|s|ing)?|regret)\b|"
    r"(?:고장|불량|문제|과열|발화|끊김|끊긴|닳는다|후회)",
    re.IGNORECASE,
)
USAGE_PATTERN = re.compile(
    r"\b(?:used?|using|owned?|tested?|after|months?|years?|long[- ]term)\b|"
    r"(?:사용|이용|개월|년째|장기)",
    re.IGNORECASE,
)
NEGATION_PATTERN = re.compile(
    r"\b(?:not|never|no|without|isn['’]?t|wasn['’]?t|didn['’]?t|doesn['’]?t)\b|"
    r"(?:아니|않|없)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class CompressionResult:
    """Bounded text and whether any source text was omitted."""

    text: str
    truncated: bool


class EvidenceCompressor:
    """Select high-signal paragraphs and avoid contextless mid-sentence slices."""

    def __init__(self, policy: EvidenceBudgetPolicy) -> None:
        self._policy = policy

    def compress(self, text: str) -> CompressionResult:
        if len(text) <= self._policy.max_chars_per_source:
            return CompressionResult(text=text, truncated=False)

        paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
        if len(paragraphs) >= 3:
            bounded = self._select_paragraphs(paragraphs)
        else:
            bounded = self._safe_prefix(text, self._policy.max_chars_per_source)
        return CompressionResult(text=bounded, truncated=True)

    def _select_paragraphs(self, paragraphs: list[str]) -> str:
        limit = self._policy.max_chars_per_source
        selected_indices = self._selected_indices(paragraphs)
        separator_length = 2 * (len(selected_indices) - 1)
        per_section = max(1, (limit - separator_length) // len(selected_indices))
        sections: list[str] = []

        for index in sorted(selected_indices):
            paragraph = paragraphs[index]
            if len(paragraph) <= per_section:
                sections.append(paragraph)
            elif any(
                pattern.search(paragraph)
                for pattern in (RISK_PATTERN, USAGE_PATTERN, NEGATION_PATTERN)
            ):
                sections.append(self._safe_signal_slice(paragraph, per_section))
            elif index == len(paragraphs) - 1:
                sections.append(self._safe_suffix(paragraph, per_section))
            else:
                sections.append(self._safe_prefix(paragraph, per_section))
        return "\n\n".join(sections)[:limit].rstrip()

    @staticmethod
    def _selected_indices(paragraphs: list[str]) -> list[int]:
        scores = [
            3 * len(RISK_PATTERN.findall(paragraph))
            + 2 * len(USAGE_PATTERN.findall(paragraph))
            + len(NEGATION_PATTERN.findall(paragraph))
            for paragraph in paragraphs
        ]
        ranked = sorted(range(len(paragraphs)), key=lambda index: (-scores[index], index))
        positive = [index for index in ranked if scores[index] > 0]
        selected = positive[:3]
        fallbacks = [0, len(paragraphs) // 2, len(paragraphs) - 1]
        for index in fallbacks + ranked:
            if len(selected) >= 3:
                break
            if index not in selected:
                selected.append(index)
        return selected

    @staticmethod
    def _safe_signal_slice(text: str, limit: int) -> str:
        matches = [
            match
            for pattern in (RISK_PATTERN, USAGE_PATTERN, NEGATION_PATTERN)
            if (match := pattern.search(text)) is not None
        ]
        first_signal = min(match.start() for match in matches)
        if first_signal <= len(text) // 2:
            return EvidenceCompressor._safe_prefix(text, limit)
        return EvidenceCompressor._safe_suffix(text, limit)

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
        preceding_context = text[sentence_start:start]
        negations = list(NEGATION_PATTERN.finditer(preceding_context))
        if negations:
            negation_start = sentence_start + negations[-1].start()
            return EvidenceCompressor._safe_prefix(text[negation_start:], limit)
        boundary = text.find(" ", start)
        if boundary != -1:
            start = boundary + 1
        return f"…{text[start:].lstrip()}"
