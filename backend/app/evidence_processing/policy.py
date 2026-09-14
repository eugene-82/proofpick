"""Explicit character budgets for bounded evidence."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvidenceBudgetPolicy:
    """Maximum characters passed to claim extraction for one source."""

    max_chars_per_source: int = 4_000

    def __post_init__(self) -> None:
        if self.max_chars_per_source < 32:
            raise ValueError("max_chars_per_source must be at least 32")


DEFAULT_EVIDENCE_BUDGET_POLICY = EvidenceBudgetPolicy()
