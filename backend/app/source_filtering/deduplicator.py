"""Conservative source-copy tracking with final-state reconciliation."""

from dataclasses import dataclass

from app.reliability import strong_copy

from .models import (
    DropReason,
    FilteredSource,
    IndependenceReasonCode,
    IndependenceState,
    SourceCandidate,
)


@dataclass(frozen=True)
class DuplicateMatch:
    reason: DropReason
    representative_key: str
    independence_group_id: str
    drop: bool = True
    can_enrich: bool = False


class SourceDeduplicator:
    """Delete only URL aliases, exact bodies, and strongly supported copies."""

    def __init__(self, near_duplicate_threshold: float = 0.90) -> None:
        if not 0 <= near_duplicate_threshold <= 1:
            raise ValueError("near_duplicate_threshold must be between 0 and 1")
        self._near_duplicate_threshold = near_duplicate_threshold
        self._by_url: dict[str, tuple[str, str, bool]] = {}
        self._by_content_hash: dict[str, tuple[str, str]] = {}
        self._copy_text_by_key: dict[str, str] = {}
        self._source_by_key: dict[str, FilteredSource] = {}
        self._active_keys: set[str] = set()
        self._aliases_by_key: dict[str, set[str]] = {}

    def find_duplicate(
        self,
        normalized_url: str,
        content_hash: str | None,
        copy_text: str | None = None,
    ) -> DuplicateMatch | None:
        if (url_match := self._by_url.get(normalized_url)) is not None:
            key, group, can_enrich = url_match
            return DuplicateMatch(
                DropReason.DUPLICATE_URL,
                key,
                group,
                can_enrich=can_enrich,
            )
        if content_hash is not None and (
            match := self._by_content_hash.get(content_hash)
        ) is not None:
            return DuplicateMatch(
                DropReason.DUPLICATE_CONTENT,
                match[0],
                match[1],
            )
        if copy_text:
            for source_key in sorted(self._active_keys):
                remembered = self._copy_text_by_key.get(source_key)
                if remembered and strong_copy(
                    remembered, copy_text, self._near_duplicate_threshold
                ):
                    source = self._source_by_key[source_key]
                    return DuplicateMatch(
                        DropReason.NEAR_DUPLICATE_CONTENT,
                        source.source_key,
                        source.independence_group_id,
                    )
        return None

    def remember(self, source: FilteredSource, copy_text: str | None) -> None:
        self._source_by_key[source.source_key] = source
        self._active_keys.add(source.source_key)
        self._aliases_by_key.setdefault(source.source_key, set()).add(
            source.normalized_url
        )
        if copy_text is not None:
            self._copy_text_by_key[source.source_key] = copy_text
        self._rebuild_indexes()

    def remember_alias(self, normalized_url: str, representative_key: str) -> None:
        source = self._source_by_key[representative_key]
        self._aliases_by_key.setdefault(representative_key, set()).update(
            {normalized_url, source.normalized_url}
        )
        self._rebuild_indexes()

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
    ) -> FilteredSource:
        source = self._source_by_key[representative_key]
        self._aliases_by_key.setdefault(representative_key, set()).update(
            {source.normalized_url, normalized_url}
        )
        source.title = self._richer(source.title, candidate.title)
        source.snippet = self._richer(source.snippet, candidate.snippet)
        source.raw_content = self._richer(source.raw_content, candidate.raw_content)
        if source.published_at is None:
            source.published_at = candidate.published_at
        if normalized_url < source.normalized_url:
            source.original_url = candidate.url or normalized_url
            source.normalized_url = normalized_url
            source.domain = domain
        final_content = source.raw_content or source.snippet
        final_copy_text = copy_text if final_content in {candidate.raw_content, candidate.snippet} else None
        if final_copy_text is None:
            final_copy_text = self._copy_text_by_key.get(representative_key)
        final_dependency = dependency_text if final_copy_text == copy_text else None
        source.content_hash = fingerprint(final_dependency) if final_dependency else source.content_hash
        if final_copy_text:
            self._copy_text_by_key[representative_key] = final_copy_text
        collision = self._find_collision(representative_key, source)
        if collision is not None:
            return self._reconcile(representative_key, collision)
        self._rebuild_indexes()
        return source

    def representative(self, source_key: str) -> FilteredSource:
        return self._source_by_key[source_key]
    def active_sources(self) -> list[FilteredSource]:
        return sorted(
            (self._source_by_key[key] for key in self._active_keys),
            key=lambda source: (source.normalized_url, source.content_hash or ""),
        )

    def _find_collision(
        self, source_key: str, source: FilteredSource
    ) -> str | None:
        text = self._copy_text_by_key.get(source_key)
        for other_key in sorted(self._active_keys):
            if other_key == source_key:
                continue
            other = self._source_by_key[other_key]
            if source.content_hash and source.content_hash == other.content_hash:
                return other_key
            other_text = self._copy_text_by_key.get(other_key)
            if text and other_text and strong_copy(
                text, other_text, self._near_duplicate_threshold
            ):
                return other_key
        return None

    def _reconcile(self, left_key: str, right_key: str) -> FilteredSource:
        left = self._source_by_key[left_key]
        right = self._source_by_key[right_key]
        winner = min((left, right), key=lambda item: item.source_key)
        donor = min(
            (left, right),
            key=lambda item: (
                -(len(item.raw_content or item.snippet or "")),
                item.normalized_url,
            ),
        )
        confirmed = next(
            (
                item
                for item in (left, right)
                if item.independence_state is IndependenceState.CONFIRMED
            ),
            None,
        )
        loser = right if winner is left else left
        winner_url = winner.normalized_url
        donor_copy_text = self._copy_text_by_key.get(donor.source_key)
        if winner is not donor:
            for field in (
                "original_url",
                "normalized_url",
                "domain",
                "title",
                "snippet",
                "raw_content",
                "published_at",
                "source_type",
                "content_hash",
            ):
                setattr(winner, field, getattr(donor, field))
            if donor_copy_text:
                self._copy_text_by_key[winner.source_key] = donor_copy_text
        state_source = confirmed or donor
        winner.independence_state = state_source.independence_state
        winner.independence_reason_codes = list(
            state_source.independence_reason_codes
        )
        winner.independence_group_id = min(
            left.independence_group_id, right.independence_group_id
        )
        loser.independence_group_id = winner.independence_group_id
        loser.independence_state = IndependenceState.DEPENDENT
        loser.independence_reason_codes = [IndependenceReasonCode.DUPLICATE]
        self._active_keys.discard(loser.source_key)
        self._aliases_by_key.setdefault(winner.source_key, set()).update(
            self._aliases_by_key.pop(loser.source_key, set())
            | {loser.normalized_url, winner_url}
        )
        self._rebuild_indexes()
        return winner

    def _rebuild_indexes(self) -> None:
        self._by_url.clear()
        self._by_content_hash.clear()
        for key in sorted(self._active_keys):
            source = self._source_by_key[key]
            identity = (source.source_key, source.independence_group_id)
            self._by_url[source.normalized_url] = (*identity, True)
            for alias in self._aliases_by_key.get(key, set()):
                self._by_url[alias] = (*identity, True)
            if source.content_hash is not None:
                self._by_content_hash[source.content_hash] = identity

    @staticmethod
    def _richer(current: str | None, candidate: str | None) -> str | None:
        if candidate is None or not candidate.strip():
            return current
        if current is None or len(candidate.strip()) > len(current.strip()):
            return candidate
        return current