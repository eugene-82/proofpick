"""Cost and context policy for claim extraction."""

from dataclasses import dataclass


CLAIM_EXTRACTION_PROMPT_VERSION = "v2-semantic-verification"


@dataclass(frozen=True)
class ClaimExtractionPolicy:
    """Bounded multi-document batch limits."""

    max_documents_per_batch: int = 5
    max_total_chars_per_batch: int = 12_000

    def __post_init__(self) -> None:
        if self.max_documents_per_batch < 1:
            raise ValueError("max_documents_per_batch must be positive")
        if self.max_total_chars_per_batch < 1:
            raise ValueError("max_total_chars_per_batch must be positive")
