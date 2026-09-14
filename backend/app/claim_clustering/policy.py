"""Configurable semantic clustering policy."""

from dataclasses import dataclass


@dataclass(frozen=True)
class ClaimClusteringPolicy:
    """Threshold for similarity edges inside aspect/sentiment partitions."""

    similarity_threshold: float = 0.82

    def __post_init__(self) -> None:
        if not 0 <= self.similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
