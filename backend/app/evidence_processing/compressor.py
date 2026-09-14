"""Deterministic, extractive evidence bounding."""

from dataclasses import dataclass

from .policy import EvidenceBudgetPolicy


@dataclass(frozen=True)
class CompressionResult:
    """Bounded text and whether any source text was omitted."""

    text: str
    truncated: bool


class EvidenceCompressor:
    """Keep representative beginning, middle, and ending source text within a budget."""

    def __init__(self, policy: EvidenceBudgetPolicy) -> None:
        self._policy = policy

    def compress(self, text: str) -> CompressionResult:
        if len(text) <= self._policy.max_chars_per_source:
            return CompressionResult(text=text, truncated=False)

        paragraphs = text.split("\n\n")
        if len(paragraphs) >= 3:
            bounded = self._select_paragraphs(paragraphs)
        else:
            bounded = self._strategic_slice(text)
        return CompressionResult(text=bounded, truncated=True)

    def _select_paragraphs(self, paragraphs: list[str]) -> str:
        selected_indices = list(dict.fromkeys((0, len(paragraphs) // 2, len(paragraphs) - 1)))
        separator_length = 2 * (len(selected_indices) - 1)
        per_section = (self._policy.max_chars_per_source - separator_length) // len(selected_indices)
        sections: list[str] = []

        for index in selected_indices:
            paragraph = paragraphs[index]
            if index == 0:
                sections.append(paragraph[:per_section].rstrip())
            elif index == len(paragraphs) - 1:
                sections.append(paragraph[-per_section:].lstrip())
            else:
                sections.append(paragraph[:per_section].rstrip())
        return "\n\n".join(sections)

    def _strategic_slice(self, text: str) -> str:
        marker = "…"
        available = self._policy.max_chars_per_source - (2 * len(marker))
        head_length = available // 3
        middle_length = available // 3
        tail_length = available - head_length - middle_length
        middle_start = (len(text) - middle_length) // 2
        return (
            f"{text[:head_length].rstrip()}{marker}"
            f"{self._center_slice(text, middle_length)}{marker}"
            f"{text[-tail_length:].lstrip()}"
        )

    @staticmethod
    def _center_slice(text: str, length: int) -> str:
        if len(text) <= length:
            return text
        start = (len(text) - length) // 2
        return text[start : start + length]
