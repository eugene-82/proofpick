"""Analysis-local stable identity registry for incremental filtering runs."""

from hashlib import sha256

from .deduplicator import SourceDeduplicator


class SourceIdentityRegistry:
    def __init__(self, deduplicator: SourceDeduplicator | None = None,
                 *, analysis_id: str = "analysis-local") -> None:
        self.deduplicator = deduplicator or SourceDeduplicator()
        self.analysis_id = analysis_id
        digest = sha256(analysis_id.encode("utf-8")).hexdigest()[:16]
        self.registry_id = f"registry-{digest}"
        self.revision = 0
        self._next_source_number = 1
        self._next_group_number = 1
        self._source_keys: set[str] = set()

    def next_source_key(self) -> str:
        source_key = f"S{self._next_source_number:03d}"
        self._next_source_number += 1
        return source_key

    def next_group_id(self) -> str:
        group_id = f"IG{self._next_group_number:03d}"
        self._next_group_number += 1
        return group_id

    def record_source(self, source_key: str) -> None:
        self._source_keys.add(source_key)
        self.revision += 1

    def record_reconciliation(self) -> None:
        self.revision += 1

    def owns_source(self, source_key: str) -> bool:
        return source_key in self._source_keys
