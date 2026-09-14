"""Analysis-local stable identity registry for incremental filtering runs."""

from .deduplicator import SourceDeduplicator


class SourceIdentityRegistry:
    """Allocate collision-free IDs and reconcile duplicates across one snapshot."""

    def __init__(self, deduplicator: SourceDeduplicator | None = None) -> None:
        self.deduplicator = deduplicator or SourceDeduplicator()
        self._next_source_number = 1
        self._next_group_number = 1

    def next_source_key(self) -> str:
        source_key = f"S{self._next_source_number:03d}"
        self._next_source_number += 1
        return source_key

    def next_group_id(self) -> str:
        group_id = f"IG{self._next_group_number:03d}"
        self._next_group_number += 1
        return group_id
