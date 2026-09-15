"""Exact and conservative near-duplicate source tracking."""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from .models import DropReason, FilteredSource, SourceCandidate

NEGATION_PATTERN = re.compile(r"\b(?:not|never|no|without|isn['’]?t|wasn['’]?t|didn['’]?t)\b", re.I)
CLAIM_SIGNAL_PATTERN = re.compile(
    r"\b(?:fail(?:ed|s|ure)?|fire|overheat(?:ed|ing)?|broken|disconnect(?:ed|ing)?|"
    r"drain(?:ed|ing)?|works?|reliable|great|good|excellent)\b", re.I
)
NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")
AUTHOR_PATTERN = re.compile(r"\b(?:author|reviewer|by|user)\s*[:#-]?\s*([\w.-]+)", re.I)


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

    def find_duplicate(self, normalized_url: str, content_hash: str | None,
                       dependency_text: str | None = None) -> DuplicateMatch | None:
        url_match = self._by_url.get(normalized_url)
        if url_match is not None:
            key, group, can_enrich = url_match
            return DuplicateMatch(DropReason.DUPLICATE_URL, key, group, can_enrich=can_enrich)
        if content_hash is not None and (match := self._by_content_hash.get(content_hash)):
            return DuplicateMatch(DropReason.DUPLICATE_CONTENT, match[0], match[1])
        if dependency_text is not None and len(dependency_text.split()) >= 5:
            for source_key, remembered in self._dependency_text_by_key.items():
                if len(remembered.split()) < 5:
                    continue
                similarity = SequenceMatcher(None, remembered, dependency_text, autojunk=False).ratio()
                if similarity >= self._near_duplicate_threshold:
                    source = self._source_by_key[source_key]
                    return DuplicateMatch(
                        DropReason.NEAR_DUPLICATE_CONTENT, source.source_key,
                        source.independence_group_id,
                        drop=not self._meaningfully_different(remembered, dependency_text),
                    )
        return None

    @staticmethod
    def _meaningfully_different(left: str, right: str) -> bool:
        if bool(NEGATION_PATTERN.search(left)) != bool(NEGATION_PATTERN.search(right)):
            return True
        if set(NUMBER_PATTERN.findall(left)) != set(NUMBER_PATTERN.findall(right)):
            return True
        if set(AUTHOR_PATTERN.findall(left)) != set(AUTHOR_PATTERN.findall(right)):
            return True
        left_signals = {value.casefold() for value in CLAIM_SIGNAL_PATTERN.findall(left)}
        right_signals = {value.casefold() for value in CLAIM_SIGNAL_PATTERN.findall(right)}
        return left_signals != right_signals

    def remember(self, source: FilteredSource, dependency_text: str | None) -> None:
        identity = (source.source_key, source.independence_group_id)
        self._by_url[source.normalized_url] = (*identity, True)
        if source.content_hash is not None:
            self._by_content_hash[source.content_hash] = identity
        if dependency_text is not None:
            self._dependency_text_by_key[source.source_key] = dependency_text
        self._source_by_key[source.source_key] = source

    def remember_alias(self, normalized_url: str, representative_key: str) -> None:
        source = self._source_by_key[representative_key]
        if normalized_url == source.normalized_url:
            return
        self._by_url[normalized_url] = (representative_key, source.independence_group_id, False)

    def enrich(self, representative_key: str, candidate: SourceCandidate,
               normalize_text, fingerprint) -> FilteredSource:
        source = self._source_by_key[representative_key]
        source.title = self._richer(source.title, candidate.title)
        source.snippet = self._richer(source.snippet, candidate.snippet)
        source.raw_content = self._richer(source.raw_content, candidate.raw_content)
        if source.published_at is None:
            source.published_at = candidate.published_at
        final_content = source.raw_content or source.snippet
        final_text = normalize_text(final_content)
        source.content_hash = fingerprint(final_text)
        self.remember(source, final_text)
        return source

    @staticmethod
    def _richer(current: str | None, candidate: str | None) -> str | None:
        if candidate is None or not candidate.strip():
            return current
        if current is None or len(candidate.strip()) > len(current.strip()):
            return candidate
        return current
