"""Shared deterministic reliability primitives.

The module intentionally models only the small relation contract required by the
pipeline: clause-local subject, action, and polarity.  It is not a general NLP
classifier.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

WORD_RE = re.compile(r"[a-z0-9]+(?:['’][a-z]+)?|[가-힣]+", re.I)
SENTENCE_RE = re.compile(r"(?<=[.!?。！？])\s+|\n+")
CLAUSE_RE = re.compile(
    r"\s*(?:[;,:]|\bwhen\b|\bwhile\b|\bbecause\b|\balthough\b|\bwhereas\b|\bbut\b|\band\b(?=\s+(?:the|this|that|my|our|its)\b))\s*",
    re.I,
)
NEGATION_RE = re.compile(
    r"\b(?:not|never|no|without|isn['’]?t|wasn['’]?t|didn['’]?t|doesn['’]?t)\b|"
    r"(?:아니|않|없)",
    re.I,
)
EVENT_PATTERNS = (
    ("fire", re.compile(r"\b(?:catch|catches|caught)\s+fire\b|\bfire\b|(?:발화|불이\s*났)", re.I)),
    ("failure", re.compile(r"\b(?:fail(?:ed|s|ure)?|broke|broken|stopped\s+working)\b|(?:고장|작동[^.!?]*(?:않|멈))", re.I)),
    ("overheat", re.compile(r"\boverheat(?:ed|s|ing)?\b|(?:과열)", re.I)),
    ("disconnect", re.compile(r"\bdisconnect(?:ed|s|ing)?\b|(?:연결[^.!?]*(?:끊|실패))", re.I)),
    ("drain", re.compile(r"\bdrain(?:ed|s|ing)?\b|(?:배터리[^.!?]*(?:닳|소모))", re.I)),
    ("working", re.compile(r"\b(?:works?|worked|reliable)\b|(?:잘\s*된다|안정)", re.I)),
)
DETERMINERS = frozenset({"a", "an", "the", "this", "that", "my", "our", "its"})
SUBJECT_SKIP = frozenset(
    {
        "after", "also", "and", "before", "but", "completely", "could",
        "did", "do", "does", "eventually", "finally", "for", "had", "has",
        "have", "i", "in", "is", "just", "may", "might", "never", "not",
        "of", "on", "repeatedly", "suddenly", "to", "unexpectedly", "was",
        "we", "were", "will", "with", "would",
    }
)
PREPOSITIONS = re.compile(
    r"\b(?:beside|near|next\s+to|with|inside|outside|under|above|behind|around)\b",
    re.I,
)
COPULA_RE = re.compile(r"\b(?:is|are|was|were|had|has|have|became|felt)\b", re.I)
USAGE_RE = re.compile(r"\b(?:i|we|[A-Z][a-z]+)\s+(?:have\s+)?(?:used|owned|tested|measured|tried|carried|took)\b", re.I)
AUTHOR_RE = re.compile(
    r"\b(?:author|reviewer|by|user)\s*[:#-]?\s*([a-z][\w.-]+)|"
    r"\b([A-Z][a-z]+)\s+(?:used|owned|tested|measured|reported|observed)\b",
    re.I,
)
MEASUREMENT_RE = re.compile(
    r"\b(\d+(?:\.\d+)?|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*"
    r"(hours?|days?|weeks?|months?|years?|mah|wh)\b",
    re.I,
)


@dataclass(frozen=True, order=True)
class EventRelation:
    subject: str
    predicate: str
    negated: bool


def sentences(text: str) -> list[str]:
    return [part.strip() for part in SENTENCE_RE.split(text) if part.strip()]


def clauses(text: str) -> list[str]:
    result: list[str] = []
    for sentence in sentences(text):
        result.extend(part.strip() for part in CLAUSE_RE.split(sentence) if part.strip())
    return result


def _antecedent_candidates(text: str | None, current: str) -> set[str]:
    if not text:
        return set()
    prior = sentences(text)
    normalized_current = normalize_text(current)
    while prior and normalize_text(prior[-1]) == normalized_current:
        prior.pop()
    if not prior:
        return set()
    nearest = prior[-1]
    candidates = {
        match.group(1).casefold()
        for match in re.finditer(r"\b(?:the|this|that|my|our)\s+([a-z][\w-]*)", nearest, re.I)
    }
    subject_part = COPULA_RE.split(nearest, maxsplit=1)[0]
    subject_tokens = [token.casefold() for token in WORD_RE.findall(subject_part)]
    candidates.update(
        token for token in subject_tokens
        if token not in DETERMINERS and token not in SUBJECT_SKIP and not token.endswith("ly")
    )
    return candidates


def _subject(clause: str, predicate_start: int, antecedent: str | None) -> str | None:
    prefix = clause[:predicate_start].strip()
    korean = re.findall(r"([가-힣]+?)(?:이|가)\s*$", prefix)
    if korean:
        return korean[-1]
    tokens = [token.casefold() for token in WORD_RE.findall(prefix)]
    meaningful = [
        token for token in tokens
        if token not in DETERMINERS and token not in SUBJECT_SKIP and not token.endswith("ly")
    ]
    if tokens and tokens[0] in {"it", "this", "that"}:
        candidates = _antecedent_candidates(antecedent, clause)
        return next(iter(candidates)) if len(candidates) == 1 else None
    possessive = re.search(
        r"\b(?:the\s+)?[a-z][\w-]*['’]s\s+([a-z][\w-]*)\b",
        prefix,
        re.I,
    )
    if possessive:
        return possessive.group(1).casefold()
    local_prefix = PREPOSITIONS.split(prefix, maxsplit=1)[0]
    local_tokens = [token.casefold() for token in WORD_RE.findall(local_prefix)]
    local = [
        token for token in local_tokens
        if token not in DETERMINERS and token not in SUBJECT_SKIP and not token.endswith("ly")
    ]
    return local[-1] if local else (meaningful[-1] if meaningful else None)


def extract_relations(text: str, *, antecedent: str | None = None) -> tuple[EventRelation, ...]:
    found: set[EventRelation] = set()
    for clause in clauses(text):
        for predicate, pattern in EVENT_PATTERNS:
            for match in pattern.finditer(clause):
                subject = _subject(clause, match.start(), antecedent)
                if subject is None:
                    continue
                negated = bool(NEGATION_RE.search(clause[: match.start()]))
                found.add(EventRelation(subject, predicate, negated))
    return tuple(sorted(found))


def relation_supported(claim: str, evidence: str, *, antecedent: str | None = None) -> bool:
    claim_relations = extract_relations(claim, antecedent=antecedent)
    if not claim_relations:
        return not any(pattern.search(claim) for _, pattern in EVENT_PATTERNS)
    evidence_relations = set(extract_relations(evidence, antecedent=antecedent))
    return all(relation in evidence_relations for relation in claim_relations)


def observation_spans(text: str) -> tuple[str, ...]:
    """Return claim-bearing spans with adjacent direct-observation context."""
    units = sentences(text)
    spans: list[str] = []
    for index, unit in enumerate(units):
        if not extract_relations(unit):
            continue
        span = unit
        if index and USAGE_RE.search(units[index - 1]):
            span = f"{units[index - 1]} {unit}"
        spans.append(normalize_text(span))
    return tuple(spans)


def has_distinct_observation(text: str) -> bool:
    return any(
        len(WORD_RE.findall(span)) >= 6 and USAGE_RE.search(span)
        for span in observation_spans(text)
    )


def strong_copy(left: str, right: str, threshold: float) -> bool:
    left_authors = {value.casefold() for groups in AUTHOR_RE.findall(left) for value in groups if value}
    right_authors = {value.casefold() for groups in AUTHOR_RE.findall(right) for value in groups if value}
    if left_authors != right_authors:
        return False
    left_measurements = {(number, unit.casefold()) for number, unit in MEASUREMENT_RE.findall(left)}
    right_measurements = {(number, unit.casefold()) for number, unit in MEASUREMENT_RE.findall(right)}
    if left_measurements != right_measurements:
        return False
    left_relations = set(extract_relations(left))
    right_relations = set(extract_relations(right))
    if left_relations != right_relations or not left_relations:
        return False
    for left_span in observation_spans(left):
        if len(WORD_RE.findall(left_span)) < 6:
            continue
        for right_span in observation_spans(right):
            if len(WORD_RE.findall(right_span)) < 6:
                continue
            if SequenceMatcher(None, left_span, right_span, autojunk=False).ratio() >= threshold:
                return True
    return False


def normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())