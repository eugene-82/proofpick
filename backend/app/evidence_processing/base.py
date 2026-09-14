"""Evidence-processing interface."""

from abc import ABC, abstractmethod

from app.source_filtering.models import FilteredSource

from .models import EvidenceDocument


class EvidenceProcessor(ABC):
    """Clean and bound accepted source text without semantic interpretation."""

    @abstractmethod
    def process(self, source: FilteredSource) -> EvidenceDocument | None:
        """Return bounded evidence, or None if no usable text remains."""
