"""Exact identity merging and final-state dependency reconciliation."""

from dataclasses import dataclass

from .models import (
    DropReason,
    FilteredSource,
    IndependenceReasonCode,
    IndependenceState,
    SourceCandidate,
)
from .normalizer import SourceNormalizer


@dataclass(frozen=True)
class DuplicateMatch:
    reason: DropReason
    representative_key: str
    independence_group_id: str
    drop: bool = True
    can_enrich: bool = False


class SourceDeduplicator:
    """Merge exact identity only; preserve near-copies in dependency groups."""

    def __init__(self, near_duplicate_threshold: float = 0.90) -> None:
        if not 0 <= near_duplicate_threshold <= 1:
            raise ValueError("near_duplicate_threshold must be between 0 and 1")
        self._near_duplicate_threshold = near_duplicate_threshold
        self._normalizer = SourceNormalizer()
        self._source_by_key: dict[str, FilteredSource] = {}
        self._active_keys: set[str] = set()
        self._aliases_by_key: dict[str, set[str]] = {}
        self._copy_text_by_key: dict[str, str] = {}
        self._declared_state: dict[str, IndependenceState] = {}
        self._redirects: dict[str, str] = {}
        self._by_url: dict[str, str] = {}
        self._by_content_hash: dict[str, str] = {}

    def find_duplicate(
        self,
        normalized_url: str,
        content_hash: str | None,
        copy_text: str | None = None,
    ) -> DuplicateMatch | None:
        del copy_text  # Near-copy evidence is preserved and reconciled later.
        if (key := self._by_url.get(normalized_url)) is not None:
            source = self.representative(key)
            return DuplicateMatch(
                DropReason.DUPLICATE_URL,
                key,
                source.independence_group_id,
                can_enrich=True,
            )
        if content_hash is not None and (
            key := self._by_content_hash.get(content_hash)
        ) is not None:
            source = self.representative(key)
            return DuplicateMatch(
                DropReason.DUPLICATE_CONTENT,
                key,
                source.independence_group_id,
                can_enrich=True,
            )
        return None

    def remember(
        self,
        source: FilteredSource,
        copy_text: str | None,
        *,
        declared_state: IndependenceState = IndependenceState.UNKNOWN,
    ) -> None:
        self._source_by_key[source.source_key] = source
        self._active_keys.add(source.source_key)
        self._aliases_by_key[source.source_key] = {
            source.normalized_url,
            *source.url_aliases,
        }
        if copy_text:
            self._copy_text_by_key[source.source_key] = copy_text
        self._declared_state[source.source_key] = declared_state
        self.reconcile()

    def remember_alias(self, normalized_url: str, representative_key: str) -> None:
        key = self._canonical_key(representative_key)
        self._aliases_by_key.setdefault(key, set()).add(normalized_url)
        self.reconcile()

    def enrich(
        self,
        representative_key: str,
        candidate: SourceCandidate,
        *,
        normalized_url: str,
        domain: str,
        copy_text: str | None,
        dependency_text: str | None,
        fingerprint,
        declared_state: IndependenceState = IndependenceState.UNKNOWN,
    ) -> FilteredSource:
        del dependency_text, fingerprint
        key = self._canonical_key(representative_key)
        source = self._source_by_key[key]
        self._aliases_by_key.setdefault(key, set()).update(
            {source.normalized_url, normalized_url}
        )
        source.title = self._richer(source.title, candidate.title)
        source.snippet = self._richer(source.snippet, candidate.snippet)
        source.raw_content = self._richer(source.raw_content, candidate.raw_content)
        source.published_at = self._earlier(
            source.published_at, candidate.published_at
        )
        candidate_original = candidate.url or normalized_url
        if (
            normalized_url < source.normalized_url
            or (
                normalized_url == source.normalized_url
                and candidate_original < source.original_url
            )
        ):
            source.original_url = candidate_original
            source.normalized_url = normalized_url
            source.domain = domain
        final_text = self._normalizer.copy_text(source.raw_content or source.snippet)
        if final_text:
            self._copy_text_by_key[key] = final_text
        source.content_hash = self._normalizer.exact_visible_content_fingerprint(
            source.raw_content
        )
        self._declared_state[key] = self._merge_state(
            self._declared_state.get(key, IndependenceState.UNKNOWN),
            declared_state,
        )
        self.reconcile()
        return self.representative(key)

    def representative(self, source_key: str) -> FilteredSource:
        return self._source_by_key[self._canonical_key(source_key)]

    def active_sources(self) -> list[FilteredSource]:
        return sorted(
            (self._source_by_key[key] for key in self._active_keys),
            key=lambda source: (source.normalized_url, source.source_key),
        )

    def reconcile(self) -> None:
        """Recompute exact representatives and dependency groups from final content."""
        self._collapse_exact_content()
        keys = sorted(
            self._active_keys,
            key=lambda key: (
                self._source_by_key[key].normalized_url,
                key,
            ),
        )
        adjacency = {key: set() for key in keys}
        for index, left_key in enumerate(keys):
            for right_key in keys[index + 1 :]:
                if self._normalizer.containment_copy(
                    self._copy_text_by_key.get(left_key),
                    self._copy_text_by_key.get(right_key),
                    threshold=self._near_duplicate_threshold,
                ):
                    adjacency[left_key].add(right_key)
                    adjacency[right_key].add(left_key)

        components: list[list[str]] = []
        remaining = set(keys)
        while remaining:
            root = min(
                remaining,
                key=lambda key: (self._source_by_key[key].normalized_url, key),
            )
            stack = [root]
            component: list[str] = []
            remaining.remove(root)
            while stack:
                current = stack.pop()
                component.append(current)
                for neighbor in sorted(adjacency[current], reverse=True):
                    if neighbor in remaining:
                        remaining.remove(neighbor)
                        stack.append(neighbor)
            components.append(component)
        components.sort(
            key=lambda component: min(
                self._source_by_key[key].normalized_url for key in component
            )
        )
        # Public identities describe the final source set, not arrival order.
        for number, key in enumerate(keys, start=1):
            self._source_by_key[key].source_key = f"S{number:03d}"

        key_order = {key: self._source_by_key[key].source_key for key in keys}

        for number, component in enumerate(components, start=1):
            group_id = f"IG{number:03d}"
            confirmed_keys = [
                key
                for key in component
                if self._declared_state.get(key) is IndependenceState.CONFIRMED
            ]
            representative_key = min(
                confirmed_keys or component,
                key=lambda key: (
                    self._source_by_key[key].normalized_url,
                    key_order[key],
                ),
            )
            group_confirmed = bool(confirmed_keys)
            representative_url = self._source_by_key[representative_key].normalized_url
            for key in component:
                source = self._source_by_key[key]
                source.independence_group_id = group_id
                source.dependency_representative_url = representative_url
                source.copy_fingerprint = self._normalizer.copy_fingerprint(
                    self._copy_text_by_key.get(key)
                )
                source.url_aliases = sorted(self._aliases_by_key.get(key, set()))
                if len(component) > 1 and key != representative_key:
                    source.independence_state = IndependenceState.DEPENDENT
                    source.independence_reason_codes = [
                        IndependenceReasonCode.POSSIBLE_NEAR_DUPLICATE
                    ]
                elif group_confirmed:
                    source.independence_state = IndependenceState.CONFIRMED
                    source.independence_reason_codes = [
                        IndependenceReasonCode.DISTINCT_SUBSTANTIVE_CONTENT
                    ]
                elif (
                    self._declared_state.get(key)
                    is IndependenceState.DEPENDENT
                ):
                    source.independence_state = IndependenceState.DEPENDENT
                    source.independence_reason_codes = [
                        IndependenceReasonCode.DUPLICATE
                    ]
                else:
                    source.independence_state = IndependenceState.UNKNOWN
                    source.independence_reason_codes = [
                        IndependenceReasonCode.INSUFFICIENT_CONTENT
                    ]
        self._rebuild_indexes()

    def _collapse_exact_content(self) -> None:
        groups: dict[str, list[str]] = {}
        for key in self._active_keys:
            content_hash = self._source_by_key[key].content_hash
            if content_hash:
                groups.setdefault(content_hash, []).append(key)
        for keys in groups.values():
            if len(keys) < 2:
                continue
            winner = min(
                keys,
                key=lambda key: (self._source_by_key[key].normalized_url, key),
            )
            for loser in keys:
                if loser == winner or loser not in self._active_keys:
                    continue
                self._merge_exact_source(winner, loser)
                self._aliases_by_key.setdefault(winner, set()).update(
                    self._aliases_by_key.pop(loser, set())
                )
                self._declared_state[winner] = self._merge_state(
                    self._declared_state.get(winner, IndependenceState.UNKNOWN),
                    self._declared_state.get(loser, IndependenceState.UNKNOWN),
                )
                self._redirects[loser] = winner
                self._active_keys.remove(loser)

    def _canonical_key(self, source_key: str) -> str:
        seen: set[str] = set()
        while source_key in self._redirects and source_key not in seen:
            seen.add(source_key)
            source_key = self._redirects[source_key]
        return source_key

    def _rebuild_indexes(self) -> None:
        self._by_url.clear()
        self._by_content_hash.clear()
        for key in sorted(self._active_keys):
            source = self._source_by_key[key]
            for alias in self._aliases_by_key.get(key, {source.normalized_url}):
                self._by_url[alias] = key
            if source.content_hash:
                self._by_content_hash[source.content_hash] = key

    def _merge_exact_source(self, winner: str, loser: str) -> None:
        retained = self._source_by_key[winner]
        duplicate = self._source_by_key[loser]
        retained.title = self._richer(retained.title, duplicate.title)
        retained.snippet = self._richer(retained.snippet, duplicate.snippet)
        retained.raw_content = self._richer(
            retained.raw_content, duplicate.raw_content
        )
        retained.published_at = self._earlier(
            retained.published_at, duplicate.published_at
        )
        final_text = self._normalizer.copy_text(
            retained.raw_content or retained.snippet
        )
        if final_text:
            self._copy_text_by_key[winner] = final_text
        self._copy_text_by_key.pop(loser, None)

    @staticmethod
    def _merge_state(
        left: IndependenceState, right: IndependenceState
    ) -> IndependenceState:
        if IndependenceState.CONFIRMED in {left, right}:
            return IndependenceState.CONFIRMED
        if IndependenceState.DEPENDENT in {left, right}:
            return IndependenceState.DEPENDENT
        return IndependenceState.UNKNOWN

    @staticmethod
    def _earlier(current, candidate):
        values = [value for value in (current, candidate) if value is not None]
        return min(values, key=lambda value: value.isoformat()) if values else None

    @staticmethod
    def _richer(current: str | None, candidate: str | None) -> str | None:
        values = [
            value for value in (current, candidate)
            if value is not None and value.strip()
        ]
        if not values:
            return None
        return min(values, key=lambda value: (-len(value.strip()), value.strip()))