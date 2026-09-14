"""Deterministic URL and content normalization."""

from hashlib import sha256
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .exceptions import InvalidSourceUrlError


TRACKING_PARAMETERS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_content",
        "utm_term",
        "gclid",
        "fbclid",
    }
)


class SourceNormalizer:
    """Normalize stable URL identity and exact content fingerprints."""

    def normalize_url(self, url: str | None) -> str:
        if url is None or not url.strip() or any(character.isspace() for character in url):
            raise InvalidSourceUrlError("source URL is missing or contains whitespace")

        try:
            parsed = urlsplit(url.strip())
            scheme = parsed.scheme.casefold()
            hostname = parsed.hostname
            port = parsed.port
        except ValueError as error:
            raise InvalidSourceUrlError("source URL is malformed") from error

        if scheme not in {"http", "https"} or hostname is None:
            raise InvalidSourceUrlError("source URL must be an absolute HTTP(S) URL")
        if parsed.username is not None or parsed.password is not None:
            raise InvalidSourceUrlError("source URL must not contain credentials")

        hostname = hostname.casefold().removeprefix("www.")
        try:
            hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError as error:
            raise InvalidSourceUrlError("source URL hostname is invalid") from error

        default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
        host_for_url = f"[{hostname}]" if ":" in hostname else hostname
        netloc = host_for_url if port is None or default_port else f"{host_for_url}:{port}"

        path = parsed.path.rstrip("/")
        query_pairs = [
            (key, value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
            if key.casefold() not in TRACKING_PARAMETERS
        ]
        query_pairs.sort(key=lambda item: (item[0], item[1]))
        query = urlencode(query_pairs, doseq=True)

        return urlunsplit((scheme, netloc, path, query, ""))

    def content_fingerprint(self, content: str | None) -> str | None:
        if content is None:
            return None
        normalized_content = " ".join(content.split())
        if not normalized_content:
            return None
        return sha256(normalized_content.encode("utf-8")).hexdigest()

    def domain_from_url(self, normalized_url: str) -> str:
        hostname = urlsplit(normalized_url).hostname
        if hostname is None:
            raise InvalidSourceUrlError("normalized source URL has no hostname")
        return hostname.casefold()
