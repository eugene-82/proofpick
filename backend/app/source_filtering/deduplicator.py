"""Exact and conservative near-duplicate source tracking."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .models import (
    DropReason,
    FilteredSource,
    IndependenceReasonCode,
    IndependenceState,
    SourceCandidate,
)

NEGATION_PATTERN = re.compile(
    r"\b(?:not|never|no|without|isn['’]?t|wasn['’]?t|didn['’]?t)\b", re.I
)
CLAIM_SIGNAL_PATTERN = re.compile(
    r"\b(?:fail(?:ed|s|ure)?|fire|overheat(?:ed|ing)?|broken|disconnect(?:ed|ing)?|"
    r"drain(?:ed|ing)?|works?|reliable|great|good|excellent)\b", re.I
)
NUMBER_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*(?:hours?|days?|weeks?|months?|years?|mah|wh)\b", re.I
)
AUTHOR_PATTERN = re.compile(
    r"\b(?:author|reviewer|by|user)\s*[:#-]?\s*([\w.-]+)", re.I
)
EVENT_PATTERN = re.compile(
    r"\b(fail(?:ed|s|ure)?|catch(?:es|caught)?\s+fire|fire|overheat(?:ed|s|ing)?|"
    r"broken|disconnect(?:ed|s|ing)?|drain(?:ed|s|ing)?|works?|reliable)\b",
    re.I,
)
SUBJECT_SKIP = frozenset(
    {
        "a", "an", "and", "after", "before", "but", "for", "i", "in", "it",
        "my", "of", "on", "the", "this", "to", "was", "we", "with", "never", "not",
    }
)


@dataclass(frozen=True)
class DuplicateMatch:
    reason: DropReason
    representative_key: str
    independence_group_id: str
    drop: bool = True
    can_enrich: bool = False


class SourceDeduplicator:
    def __init__(self, near_duplicate_threshold: float = 0.90) -> None:
        if not 0 <= near_duplicate_threshold <= 1:
            raise ValueError("near_duplicate_threshold must be between 0 and 1")
        self._near_duplicate_threshold = near_duplicate_threshold
        self._by_url: dict[str, tuple[str, str, bool]] = {}
        self._by_content_hash: dict[str, tuple[str, str]] = {}
        self._dependency_text_by_key: dict[str, str] = {}
        self._source_by_key: dict[str, FilteredSource] = {}
        self._active_keys: set[str] = set()
        self._aliases_by_key: dict[str, set[str]] = {}

    def find_duplicate(
        self,
        normalized_url: str,
        content_hash: str | None,
        dependency_text: str | None = None,
    ) -> DuplicateMatch | None:
        url_match = self._by_url.get(normalized_url)
        if url_match is not None:
            key, group, can_enrich = url_match
            return DuplicateMatch(
                DropReason.DUPLICATE_URL, key, group, can_enrich=can_enrich
            )
        if content_hash is not None and (
            match := self._by_content_hash.get(content_hash)
        ):
            return DuplicateMatch(
                DropReason.DUPLICATE_CONTENT, match[0], match[1]
            )
        if dependency_text is not None and len(dependency_text.split()) >= 5:
            for source_key in sorted(self._active_keys):
                remembered = self._dependency_text_by_key.get(source_key, "")
                if len(remembered.split()) < 5:
                    continue
                materially_different = self._meaningfully_different(
                    remembered, dependency_text
                )
                same_observation = self._same_observation(
                    remembered, dependency_text
                )
                similarity = SequenceMatcher(
                    None, remembered, dependency_text, autojunk=False
                ).ratio()
                if same_observation or similarity >= self._near_duplicate_threshold:
                    source = self._source_by_key[source_key]
                    return DuplicateMatch(
                        DropReason.NEAR_DUPLICATE_CONTENT,
                        source.source_key,
                        source.independence_group_id,
                        drop=not materially_different,
                    )
        return None

    @staticmethod
    def _meaningfully_different(left: str, right: str) -> bool:
        if bool(NEGATION_PATTERN.search(left)) != bool(NEGATION_PATTERN.search(right)):
            return True
        if set(NUMBER_PATTERN.findall(left)) != set(NUMBER_PATTERN.findall(right)):
            return True
        left_authors = {value.casefold() for value in AUTHOR_PATTERN.findall(left)}
        right_authors = {value.casefold() for value in AUTHOR_PATTERN.findall(right)}
        if left_authors != right_authors:
            return True
        left_signals = {value.casefold() for value in CLAIM_SIGNAL_PATTERN.findall(left)}
        right_signals = {value.casefold() for value in CLAIM_SIGNAL_PATTERN.findall(right)}
        if left_signals != right_signals:
            return True
        left_events = SourceDeduplicator._event_profile(left)
        right_events = SourceDeduplicator._event_profile(right)
        return bool(left_events and right_events and left_events != right_events)

    @staticmethod
    def _event_profile(text: str) -> frozenset[tuple[str, str | None, bool]]:
        events: set[tuple[str, str | None, bool]] = set()
        for sentence in re.split(r"(?<=[.!?])\s+|\n+", text.casefold()):
            for match in EVENT_PATTERN.finditer(sentence):
                prefix = sentence[: match.start()]
                clause = re.split(
                    r"[;,:]|\b(?:and|but|then|while)\b", prefix
                )[-1]
                tokens = re.findall(r"[a-z0-9_-]+", clause)
                subject = next(
                    (
                        token
                        for token in tokens
                        if token not in SUBJECT_SKIP and not token.isdigit()
                    ),
                    None,
                )
                predicate = re.sub(r"\s+", " ", match.group(1).casefold())
                if predicate.startswith("fail") or predicate == "broken":
                    predicate = "failure"
                elif "fire" in predicate:
                    predicate = "fire"
                elif predicate.startswith("overheat"):
                    predicate = "overheat"
                elif predicate.startswith("disconnect"):
                    predicate = "disconnect"
                elif predicate.startswith("drain"):
                    predicate = "drain"
                elif predicate.startswith("work") or predicate == "reliable":
                    predicate = "working"
                negated = bool(NEGATION_PATTERN.search(prefix[-40:]))
                events.add((predicate, subject, negated))
        return frozenset(events)

    @staticmethod
    def _material_profile(text: str) -> tuple[object, ...]:
        return (
            SourceDeduplicator._event_profile(text),
            frozenset(NUMBER_PATTERN.findall(text)),
            frozenset(
                value.casefold() for value in AUTHOR_PATTERN.findall(text)
            ),
        )

    @classmethod
    def _same_observation(cls, left: str, right: str) -> bool:
        left_profile = cls._material_profile(left)
        return left_profile == cls._material_profile(right) and any(left_profile)

    def remember(self, source: FilteredSource, dependency_text: str | None) -> None:
        self._source_by_key[source.source_key] = source
        self._active_keys.add(source.source_key)
        self._aliases_by_key.setdefault(source.source_key, set()).add(
            source.normalized_url
        )
        if dependency_text is not None:
            self._dependency_text_by_key[source.source_key] = dependency_text
        self._rebuild_indexes()

    def remember_alias(self, normalized_url: str, representative_key: str) -> None:
        source = self._source_by_key[representative_key]
        if normalized_url == source.normalized_url:
            return
        self._aliases_by_key.setdefault(representative_key, set()).add(
            normalized_url
        )
        self._rebuild_indexes()

    def enrich(
        self,
        representative_key: str,
        candidate: SourceCandidate,
        normalize_text,
        fingerprint,
    ) -> FilteredSource:
        source = self._source_by_key[representative_key]
        source.title = self._richer(source.title, candidate.title)
        source.snippet = self._richer(source.snippet, candidate.snippet)
        source.raw_content = self._richer(source.raw_content, candidate.raw_content)
        if source.published_at is None:
            source.published_at = candidate.published_at
        final_content = source.raw_content or source.snippet
        final_text = normalize_text(final_content)
        source.content_hash = fingerprint(final_text)
        self._dependency_text_by_key[representative_key] = final_text
        collision = self._find_content_collision(
            representative_key, source, final_text
        )
        if collision is not None:
            return self._reconcile(representative_key, collision)
        self._rebuild_indexes()
        return source

    def active_sources(self) -> list[FilteredSource]:
        return sorted(
            (self._source_by_key[key] for key in self._active_keys),
            key=lambda source: (source.normalized_url, source.source_key),
        )

    def _find_content_collision(
        self,
        source_key: str,
        source: FilteredSource,
        dependency_text: str,
    ) -> str | None:
        for other_key in sorted(self._active_keys):
            if other_key == source_key:
                continue
            other = self._source_by_key[other_key]
            other_text = self._dependency_text_by_key.get(other_key, "")
            if source.content_hash and source.content_hash == other.content_hash:
                return other_key
            if not self._meaningfully_different(dependency_text, other_text):
                same_observation = self._same_observation(
                    dependency_text, other_text
                )
                similarity = SequenceMatcher(
                    None, dependency_text, other_text, autojunk=False
                ).ratio()
                if same_observation or similarity >= self._near_duplicate_threshold:
                    return other_key
        return None

    def _reconcile(self, left_key: str, right_key: str) -> FilteredSource:
        left = self._source_by_key[left_key]
        right = self._source_by_key[right_key]
        winner = min(
            (left, right),
            key=lambda item: (
                item.independence_state is not IndependenceState.CONFIRMED,
                item.normalized_url,
                item.source_key,
            ),
        )
        loser = right if winner is left else left
        winner.independence_group_id = min(
            left.independence_group_id, right.independence_group_id
        )
        loser.independence_group_id = winner.independence_group_id
        loser.independence_state = IndependenceState.DEPENDENT
        loser.independence_reason_codes = [IndependenceReasonCode.DUPLICATE]
        self._active_keys.discard(loser.source_key)
        self._aliases_by_key.setdefault(winner.source_key, set()).update(
            self._aliases_by_key.pop(loser.source_key, set())
            | {loser.normalized_url}
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
                if alias != source.normalized_url:
                    self._by_url[alias] = (*identity, False)
            if source.content_hash is not None:
                self._by_content_hash[source.content_hash] = identity

    @staticmethod
    def _richer(current: str | None, candidate: str | None) -> str | None:
        if candidate is None or not candidate.strip():
            return current
        if current is None or len(candidate.strip()) > len(current.strip()):
            return candidate
        return current
