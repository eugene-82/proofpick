"""Analysis-local stable identity registry for incremental filtering runs."""

from hashlib import sha256

from .deduplicator import SourceDeduplicator


class SourceIdentityRegistry:
    def __init__(
        self,
        deduplicator: SourceDeduplicator | None = None,
        *,
        analysis_id: str = "analysis-local",
    ) -> None:
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

    def record_source(self, source_key: str, group_id: str | None = None) -> None:
        self._source_keys.add(source_key)
        self.revision += 1

    def record_reconciliation(self) -> None:
        self.revision += 1

    def owns_source(self, source_key: str) -> bool:
        return any(
            source.source_key == source_key
            for source in self.retained_sources()
        )

    def owns_identity(self, source_key: str, group_id: str) -> bool:
        active = {
            source.source_key: source.independence_group_id
            for source in self.retained_sources()
        }
        return active.get(source_key) == group_id

    def identities(self) -> tuple[tuple[str, str], ...]:
        return tuple(
            (source.source_key, source.independence_group_id)
            for source in self.retained_sources()
        )

    def retained_sources(self):
        return self.deduplicator.active_sources()

    def manifest_entries(
        self,
    ) -> tuple[
        tuple[
            str, str, str, str | None, str | None, str | None, tuple[str, ...]
        ],
        ...,
    ]:
        return tuple(
            sorted(
                (
                    source.source_key,
                    source.independence_group_id,
                    source.normalized_url,
                    source.content_hash,
                    source.copy_fingerprint,
                    source.dependency_representative_url,
                    tuple(sorted(source.url_aliases)),
                )
                for source in self.retained_sources()
            )
        )
