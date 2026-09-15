"""Deterministic source filtering with conservative dependency tracking."""
from .base import SourceFilter
from .deduplicator import DuplicateMatch, SourceDeduplicator
from .exceptions import InvalidSourceUrlError
from .models import (
    DropReason, DroppedSource, FilteredSource, IndependenceReasonCode,
    IndependenceState, SourceCandidate, SourceFilterResult, SourceType,
)
from .normalizer import SourceNormalizer
from .registry import SourceIdentityRegistry
from .service import DeterministicSourceFilter
__all__ = [
    "DeterministicSourceFilter", "DropReason", "DroppedSource", "DuplicateMatch",
    "FilteredSource", "IndependenceReasonCode", "IndependenceState",
    "InvalidSourceUrlError", "SourceCandidate", "SourceDeduplicator", "SourceFilter",
    "SourceFilterResult", "SourceIdentityRegistry", "SourceNormalizer", "SourceType",
]
