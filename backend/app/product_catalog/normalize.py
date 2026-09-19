"""Conservative normalization for exact demo-catalog aliases."""

import re
import unicodedata


_DASH_TRANSLATION = str.maketrans(
    {character: "-" for character in "‐‑‒–—―﹘﹣－"}
)
_SAFE_SEPARATOR_RE = re.compile(r"\s*-\s*|\s+")


def normalize_catalog_alias(value: str) -> str:
    """Normalize safe presentation differences without dropping identity tokens."""

    if not isinstance(value, str):
        return ""
    normalized = unicodedata.normalize("NFKC", value).translate(_DASH_TRANSLATION)
    normalized = _SAFE_SEPARATOR_RE.sub(" ", normalized.strip().casefold())
    return normalized.strip()

