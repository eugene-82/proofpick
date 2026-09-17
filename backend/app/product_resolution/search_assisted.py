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


def _compact(token: str) -> str:
    return "".join(character for character in token.casefold() if character.isalnum())


def _surface_terms(value: str) -> frozenset[str]:
    return frozenset(_compact(token) for token in _TOKEN_RE.findall(value))


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
        supporting = self.supporting_results(
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
        """Return only results whose title/URL identity matches every input term."""

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

    @staticmethod
    def _primary_identity_terms(result: SearchResult) -> frozenset[str]:
        parsed = urlsplit(str(result.url))
        path = unquote(parsed.path.replace("/", " "))
        return _surface_terms(f"{result.title or ''} {path}")

    @staticmethod
    def _fallback_identity_terms(result: SearchResult) -> frozenset[str]:
        if result.title:
            return frozenset()
        content = result.snippet or result.raw_content or ""
        return _surface_terms(content[:500])
