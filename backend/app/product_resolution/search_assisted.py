"""Conservative search-assisted confirmation for explicit model-like input."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import unquote, urlsplit

from app.search.models import SearchResult

from .models import ProductResolution


_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")
_COMPARISON_RE = re.compile(r"\b(?:vs|versus|compare|comparison)\b|비교", re.I)
_GENERIC_LEADERS = frozenset(
    {
        "best",
        "cheap",
        "good",
        "great",
        "latest",
        "new",
        "recommended",
        "top",
    }
)
_ACCESSORY_TERMS = frozenset(
    {"case", "cover", "replacement", "strap", "tips"}
)
_IDENTITY_PREFIX_STOPWORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "for",
        "my",
        "new",
        "of",
        "our",
        "the",
        "this",
        "used",
        "using",
        "with",
    }
)


def _compact(token: str) -> str:
    return "".join(character for character in token.casefold() if character.isalnum())


def _surface_terms(value: str) -> frozenset[str]:
    return frozenset(_compact(token) for token in _TOKEN_RE.findall(value))


def _surface_sequence(value: str) -> tuple[tuple[str, str], ...]:
    return tuple(
        (token, _compact(token)) for token in _TOKEN_RE.findall(value)
    )


def _is_model_like(token: str) -> bool:
    compact = _compact(token)
    has_letter = any(character.isalpha() for character in compact)
    has_digit = any(character.isdigit() for character in compact)
    return (
        (has_letter and has_digit)
        or compact.isdigit()
        or (token.isupper() and has_letter and 2 <= len(compact) <= 8)
    )


@dataclass(frozen=True)
class ProvisionalProductIdentity:
    """Input-derived candidate that is never safe until search confirms it."""

    brand: str
    product_name: str
    canonical_name: str
    required_terms: tuple[str, ...]
    family_terms: tuple[str, ...]
    model_terms: tuple[str, ...]
    model: str


class SearchAssistedIdentityResolver:
    """Confirm explicit brand/model candidates using independent result surfaces."""

    max_confirmation_results = 5
    minimum_supporting_domains = 2

    def provisional_candidate(
        self, product_input: str
    ) -> ProvisionalProductIdentity | None:
        if not isinstance(product_input, str):
            return None
        canonical_name = " ".join(product_input.strip().split())
        if (
            not canonical_name
            or len(canonical_name) > 160
            or canonical_name.casefold().startswith(("http:", "https:", "ftp:"))
            or _COMPARISON_RE.search(canonical_name)
        ):
            return None
        tokens = _TOKEN_RE.findall(canonical_name)
        if not 2 <= len(tokens) <= 6:
            return None
        normalized_tokens = tuple(_compact(token) for token in tokens)
        if (
            normalized_tokens[0] in _GENERIC_LEADERS
            or any(token in _ACCESSORY_TERMS for token in normalized_tokens[1:])
        ):
            return None
        model_pairs = [
            (token, normalized)
            for token, normalized in zip(tokens[1:], normalized_tokens[1:])
            if _is_model_like(token)
        ]
        if not model_pairs:
            return None
        model_terms = tuple(normalized for _, normalized in model_pairs)
        if (
            all(term.isdigit() for term in model_terms)
            and not tokens[0][0].isupper()
        ):
            return None
        family_terms = tuple(
            token for token in normalized_tokens if token not in model_terms
        )
        if not family_terms:
            return None
        return ProvisionalProductIdentity(
            brand=tokens[0],
            product_name=" ".join(tokens[1:]),
            canonical_name=canonical_name,
            required_terms=normalized_tokens,
            family_terms=family_terms,
            model_terms=model_terms,
            model=" ".join(token for token, _ in model_pairs),
        )

    def confirm(
        self,
        candidate: ProvisionalProductIdentity,
        results: list[SearchResult],
    ) -> ProductResolution | None:
        # Search confirmation remains stricter than downstream filtering: the
        # identity must first be established by full brand/product surfaces.
        supporting = self._confirmation_supporting_results(
            candidate,
            results,
            max_results=self.max_confirmation_results,
        )
        supporting_domains = {result.domain for result in supporting}
        conflicting_domains: set[str] = set()
        required = set(candidate.required_terms)
        family = set(candidate.family_terms)
        for result in results[: self.max_confirmation_results]:
            primary = self._primary_identity_terms(result)
            fallback = self._fallback_identity_terms(result)
            identity_terms = primary or fallback
            if not required.issubset(identity_terms) and family.issubset(
                identity_terms
            ):
                conflicting_domains.add(result.domain)

        support = len(supporting_domains)
        conflict = len(conflicting_domains)
        relevant = support + conflict
        if (
            support < self.minimum_supporting_domains
            or support <= conflict
            or relevant == 0
            or support / relevant < 2 / 3
        ):
            return None
        return ProductResolution(
            brand=candidate.brand,
            product_name=candidate.product_name,
            model=candidate.model,
            canonical_name=candidate.canonical_name,
            ambiguous=False,
            confidence=0.85,
        )

    def supporting_results(
        self,
        candidate: ProvisionalProductIdentity,
        results: list[SearchResult],
        *,
        max_results: int | None = None,
    ) -> list[SearchResult]:
        """Filter results against an already confirmed canonical identity."""

        candidates = results if max_results is None else results[:max_results]
        return [
            result
            for result in candidates
            if self._matches_confirmed_identity(candidate, result)
        ]

    def _confirmation_supporting_results(
        self,
        candidate: ProvisionalProductIdentity,
        results: list[SearchResult],
        *,
        max_results: int | None = None,
    ) -> list[SearchResult]:
        required = set(candidate.required_terms)
        candidates = results if max_results is None else results[:max_results]
        return [
            result
            for result in candidates
            if required.issubset(
                self._primary_identity_terms(result)
                or self._fallback_identity_terms(result)
            )
        ]

    def _matches_confirmed_identity(
        self,
        candidate: ProvisionalProductIdentity,
        result: SearchResult,
    ) -> bool:
        primary_text = self._primary_identity_text(result)
        primary_terms = _surface_terms(primary_text)
        body_text = self._body_identity_text(result)
        required = set(candidate.required_terms)
        product_terms = required - {_compact(candidate.brand)}

        if _COMPARISON_RE.search(primary_text):
            return False
        if self._has_explicit_competing_brand(
            candidate, f"{primary_text} {body_text}"
        ):
            return False

        if required.issubset(primary_terms):
            return True

        # An exact model/generation/variant is mandatory even when the brand is
        # omitted from a blog or community title.
        if product_terms.issubset(primary_terms):
            return True

        if not self._contains_sequence(body_text, candidate.required_terms):
            return False
        if self._is_generic_category_surface(result, primary_terms, product_terms):
            return False
        return True

    @staticmethod
    def _contains_sequence(value: str, expected: tuple[str, ...]) -> bool:
        normalized = tuple(item[1] for item in _surface_sequence(value))
        length = len(expected)
        return any(
            normalized[index:index + length] == expected
            for index in range(len(normalized) - length + 1)
        )

    @staticmethod
    def _has_explicit_competing_brand(
        candidate: ProvisionalProductIdentity,
        value: str,
    ) -> bool:
        product_sequence = tuple(candidate.required_terms[1:])
        if not product_sequence:
            return False
        surface = _surface_sequence(value)
        normalized = tuple(item[1] for item in surface)
        brand = _compact(candidate.brand)
        length = len(product_sequence)
        for index in range(len(normalized) - length + 1):
            if normalized[index:index + length] != product_sequence or index == 0:
                continue
            raw_prefix, prefix = surface[index - 1]
            if prefix == brand or prefix in _IDENTITY_PREFIX_STOPWORDS:
                continue
            if raw_prefix[:1].isupper() and raw_prefix[1:].islower():
                return True
        return False

    @staticmethod
    def _is_generic_category_surface(
        result: SearchResult,
        primary_terms: frozenset[str],
        product_terms: set[str],
    ) -> bool:
        if product_terms & primary_terms:
            return False
        title_tokens = _surface_sequence(result.title or "")
        return bool(title_tokens and title_tokens[0][1] in _GENERIC_LEADERS)

    @staticmethod
    def _primary_identity_text(result: SearchResult) -> str:
        parsed = urlsplit(str(result.url))
        path = unquote(parsed.path.replace("/", " "))
        return f"{result.title or ''} {path}"

    @staticmethod
    def _body_identity_text(result: SearchResult) -> str:
        snippet = (result.snippet or "")[:500]
        raw_content = (result.raw_content or "")[:1_000]
        return f"{snippet} {raw_content}".strip()

    @staticmethod
    def _primary_identity_terms(result: SearchResult) -> frozenset[str]:
        return _surface_terms(
            SearchAssistedIdentityResolver._primary_identity_text(result)
        )

    @staticmethod
    def _fallback_identity_terms(result: SearchResult) -> frozenset[str]:
        if result.title:
            return frozenset()
        content = result.snippet or result.raw_content or ""
        return _surface_terms(content[:500])
