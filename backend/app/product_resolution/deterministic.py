"""Small deterministic resolver for high-confidence product input patterns."""

import re
from urllib.parse import parse_qsl, unquote, urlsplit

from pydantic import HttpUrl, TypeAdapter, ValidationError

from .base import ProductResolver
from .exceptions import ProductInputError
from .models import (
    ProductCandidate,
    ProductIdentityIssue,
    ProductResolution,
)


TRACKING_PARAMETERS = frozenset(
    {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "gclid", "fbclid"}
)


class DeterministicProductResolver(ProductResolver):
    """Resolve only explicit, high-confidence patterns and preserve uncertainty."""

    _SEPARATOR_PATTERN = re.compile(r"[-_/]+")
    _URL_ADAPTER = TypeAdapter(HttpUrl)
    _WHITESPACE_PATTERN = re.compile(r"\s+")
    _COMPARISON_PATTERN = re.compile(r"\b(?:vs|versus|compare|comparison)\b|비교")
    _ACCESSORY_PATTERN = re.compile(r"\b(?:case|cover|ear\s*tips?|strap)\b|(?:케이스|커버|이어팁)")
    _AIRPODS_GENERATIONS = {
        "1st generation": (
            "airpods pro 1",
            "airpods pro 1st",
            "에어팟 프로 1",
            "에어팟 프로 1세대",
        ),
        "2nd generation": (
            "airpods pro 2",
            "airpods pro 2nd",
            "에어팟 프로 2",
            "에어팟 프로 2세대",
        ),
        "3rd generation": (
            "airpods pro 3",
            "airpods pro 3rd",
            "에어팟 프로 3",
            "에어팟 프로 3세대",
        ),
    }

    def resolve(self, product_input: str) -> ProductResolution:
        normalized_input = self._normalize_input(product_input)

        if self._contains_airpods_pro(normalized_input):
            if self._ACCESSORY_PATTERN.search(normalized_input):
                return ProductResolution(
                    ambiguous=True,
                    confidence=0,
                    identity_issues=[ProductIdentityIssue.ACCESSORY_INPUT],
                )
            return self._resolve_airpods_pro(normalized_input)
        roborock = re.search(
            r"(?:roborock|로보락)\s+q\s+revo(?:\s+(maxv|pro|plus))?\b",
            normalized_input,
        )
        if roborock:
            suffix = roborock.group(1)
            display_suffix = {"maxv": "MaxV", "pro": "Pro", "plus": "Plus"}.get(suffix)
            product_name = "Q Revo" + (f" {display_suffix}" if display_suffix else "")
            return ProductResolution(
                brand="Roborock",
                product_name=product_name,
                model=display_suffix,
                category="robot_vacuum",
                canonical_name=f"Roborock {product_name}",
                ambiguous=False,
                confidence=0.95,
            )
        if "galaxy buds3 pro" in normalized_input or "갤럭시 버즈3 프로" in normalized_input:
            return ProductResolution(
                brand="Samsung",
                product_name="Galaxy Buds3 Pro",
                category="wireless_earbuds",
                canonical_name="Samsung Galaxy Buds3 Pro",
                ambiguous=False,
                confidence=0.95,
            )
        if "galaxy buds pro" in normalized_input or "갤럭시 버즈 프로" in normalized_input:
            return self._resolve_galaxy_buds_pro()
        if "lg gram 16" in normalized_input or "lg그램16" in normalized_input:
            return ProductResolution(
                brand="LG",
                product_name="gram 16",
                category="laptop",
                canonical_name="LG gram 16",
                ambiguous=True,
                confidence=0.6,
                identity_issues=[ProductIdentityIssue.AMBIGUOUS_FAMILY],
            )

        return ProductResolution(ambiguous=True, confidence=0)

    def _normalize_input(self, product_input: str) -> str:
        if not isinstance(product_input, str):
            raise ProductInputError("product input must be a string")

        raw_input = product_input.strip()
        if not raw_input:
            raise ProductInputError("product input must not be empty")

        if raw_input.casefold().startswith(("http:", "https:", "ftp:")):
            try:
                validated_url = self._URL_ADAPTER.validate_python(raw_input)
            except ValidationError as exc:
                raise ProductInputError(
                    "product URL must be a valid http or https URL"
                ) from exc

            parsed = urlsplit(str(validated_url))
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ProductInputError(
                    "product URL must be a valid http or https URL"
                )

            parts = [parsed.hostname or ""]
            parts.extend(unquote(segment) for segment in parsed.path.split("/") if segment)
            parts.extend(
                value
                for key, value in parse_qsl(parsed.query)
                if key.casefold() not in TRACKING_PARAMETERS
            )
            return self._normalize_text(" ".join(parts))

        return self._normalize_text(raw_input)

    def _resolve_airpods_pro(self, normalized_input: str) -> ProductResolution:
        generations = [
            generation
            for generation, aliases in self._AIRPODS_GENERATIONS.items()
            if any(alias in normalized_input for alias in aliases)
        ]
        if len(generations) > 1 or self._COMPARISON_PATTERN.search(normalized_input):
            candidates = [self._airpods_candidate(item, confidence=0.5) for item in generations]
            if not candidates:
                candidates = [
                    self._airpods_candidate(item, confidence=0.34)
                    for item in self._AIRPODS_GENERATIONS
                ]
            return ProductResolution(
                brand="Apple",
                product_name="AirPods Pro",
                category="wireless_earbuds",
                canonical_name="Apple AirPods Pro",
                ambiguous=True,
                confidence=0.4,
                candidates=candidates,
                identity_issues=[ProductIdentityIssue.COMPARISON_INPUT],
            )
        if generations:
            candidate = self._airpods_candidate(generations[0], confidence=0.95)
            return ProductResolution(
                brand=candidate.brand,
                product_name=candidate.product_name,
                model=candidate.model,
                generation=candidate.generation,
                category=candidate.category,
                canonical_name=candidate.canonical_name,
                ambiguous=False,
                confidence=candidate.confidence,
            )

        return ProductResolution(
            brand="Apple",
            product_name="AirPods Pro",
            category="wireless_earbuds",
            canonical_name="Apple AirPods Pro",
            ambiguous=True,
            confidence=0.72,
            candidates=[
                self._airpods_candidate("1st generation", confidence=0.34),
                self._airpods_candidate("2nd generation", confidence=0.34),
                self._airpods_candidate("3rd generation", confidence=0.34),
            ],
            identity_issues=[ProductIdentityIssue.AMBIGUOUS_FAMILY],
        )

    @staticmethod
    def _contains_airpods_pro(value: str) -> bool:
        return "airpods pro" in value or "에어팟 프로" in value

    @staticmethod
    def _airpods_candidate(generation: str, *, confidence: float) -> ProductCandidate:
        return ProductCandidate(
            brand="Apple",
            product_name="AirPods Pro",
            generation=generation,
            category="wireless_earbuds",
            canonical_name=f"Apple AirPods Pro ({generation})",
            confidence=confidence,
        )

    @staticmethod
    def _resolve_galaxy_buds_pro() -> ProductResolution:
        return ProductResolution(
            brand="Samsung",
            product_name="Galaxy Buds Pro",
            category="wireless_earbuds",
            canonical_name="Samsung Galaxy Buds Pro",
            ambiguous=True,
            confidence=0.65,
            candidates=[
                ProductCandidate(
                    brand="Samsung",
                    product_name="Galaxy Buds Pro",
                    category="wireless_earbuds",
                    canonical_name="Samsung Galaxy Buds Pro",
                    confidence=0.34,
                ),
                ProductCandidate(
                    brand="Samsung",
                    product_name="Galaxy Buds2 Pro",
                    category="wireless_earbuds",
                    canonical_name="Samsung Galaxy Buds2 Pro",
                    confidence=0.33,
                ),
                ProductCandidate(
                    brand="Samsung",
                    product_name="Galaxy Buds3 Pro",
                    category="wireless_earbuds",
                    canonical_name="Samsung Galaxy Buds3 Pro",
                    confidence=0.33,
                ),
            ],
            identity_issues=[ProductIdentityIssue.AMBIGUOUS_FAMILY],
        )

    @classmethod
    def _normalize_text(cls, value: str) -> str:
        normalized = cls._SEPARATOR_PATTERN.sub(" ", value)
        normalized = cls._WHITESPACE_PATTERN.sub(" ", normalized)
        return normalized.strip().casefold()
