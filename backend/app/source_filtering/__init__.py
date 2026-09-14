"""Deterministic source filtering and exact deduplication."""

from .base import SourceFilter
from .deduplicator import DuplicateMatch, SourceDeduplicator
from .exceptions import InvalidSourceUrlError
from .models import (
    DropReason,
    DroppedSource,
    FilteredSource,
    SourceCandidate,
    SourceFilterResult,
    SourceType,
)
from .normalizer import SourceNormalizer
from .service import DeterministicSourceFilter

__all__ = [
    "DeterministicSourceFilter",
    "DropReason",
    "DroppedSource",
    "DuplicateMatch",
    "FilteredSource",
    "InvalidSourceUrlError",
    "SourceCandidate",
    "SourceDeduplicator",
    "SourceFilter",
    "SourceFilterResult",
    "SourceNormalizer",
    "SourceType",
]
