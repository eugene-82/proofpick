"""Deterministic URL and content normalization."""

import html
import re
from difflib import SequenceMatcher
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
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")
TOKEN_PATTERN = re.compile(r"[^\W_]+", re.UNICODE)
SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
COPY_SHINGLE_SIZE = 5
MIN_SHARED_COPY_SHINGLES = 6
MIN_SHARED_COPY_CONTEXT_TOKENS = 10
MIN_DOCUMENT_SHINGLES = 4


class SourceNormalizer:
    """Normalize stable URL identity and conservative content identity."""

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


    def exact_visible_content_fingerprint(self, content: str | None) -> str | None:
        """Hash complete visible content, never a provider-generated snippet."""
        visible = self.copy_text(content)
        return self.content_fingerprint(visible)

    @staticmethod
    def copy_tokens(content: str | None) -> tuple[str, ...]:
        if content is None:
            return ()
        visible = HTML_TAG_PATTERN.sub(" ", html.unescape(content))
        return tuple(token.casefold() for token in TOKEN_PATTERN.findall(visible))

    @classmethod
    def copy_shingles(
        cls,
        content: str | None,
        *,
        size: int = COPY_SHINGLE_SIZE,
    ) -> frozenset[tuple[str, ...]]:
        tokens = cls.copy_tokens(content)
        if len(tokens) < size:
            return frozenset()
        return frozenset(
            tuple(tokens[index : index + size])
            for index in range(len(tokens) - size + 1)
        )

    @classmethod
    def copy_fingerprint(cls, content: str | None) -> str | None:
        shingles = cls.copy_shingles(content)
        if not shingles:
            return None
        payload = "\n".join(" ".join(shingle) for shingle in sorted(shingles))
        return sha256(payload.encode("utf-8")).hexdigest()

    @classmethod
    def has_structural_document_context(cls, content: str | None) -> bool:
        """Require varied full-document context without interpreting its meaning."""
        return len(cls.copy_shingles(content)) >= MIN_DOCUMENT_SHINGLES

    @classmethod
    def containment_copy(
        cls,
        left: str | None,
        right: str | None,
        *,
        threshold: float,
    ) -> bool:
        """Detect strong contiguous copy evidence without interpreting meaning."""
        if cls._shared_leading_sentence_context(left, right):
            return True
        left_tokens = cls.copy_tokens(left)
        right_tokens = cls.copy_tokens(right)
        if not left_tokens or not right_tokens:
            return False
        match = SequenceMatcher(
            None, left_tokens, right_tokens, autojunk=False
        ).find_longest_match()
        minimum_length = min(len(left_tokens), len(right_tokens))
        if (
            match.size < MIN_SHARED_COPY_CONTEXT_TOKENS
            or match.size / minimum_length < threshold
        ):
            return False
        if match.size == minimum_length:
            return True
        if match.a == 0 and match.b == 0:
            left_tail = set(left_tokens[match.size :])
            right_tail = set(right_tokens[match.size :])
            return not (left_tail & right_tail)
        if (
            match.a + match.size == len(left_tokens)
            and match.b + match.size == len(right_tokens)
        ):
            left_prefix = set(left_tokens[: match.a])
            right_prefix = set(right_tokens[: match.b])
            return not (left_prefix & right_prefix)
        return False

    @classmethod
    def _shared_leading_sentence_context(
        cls, left: str | None, right: str | None
    ) -> bool:
        left_text = cls.copy_text(left)
        right_text = cls.copy_text(right)
        if left_text is None or right_text is None:
            return False
        left_sentences = [
            cls.copy_tokens(sentence)
            for sentence in SENTENCE_SPLIT_PATTERN.split(left_text)
            if sentence.strip()
        ]
        right_sentences = [
            cls.copy_tokens(sentence)
            for sentence in SENTENCE_SPLIT_PATTERN.split(right_text)
            if sentence.strip()
        ]
        shared_tokens = 0
        for left_sentence, right_sentence in zip(
            left_sentences, right_sentences
        ):
            if not left_sentence or left_sentence != right_sentence:
                break
            shared_tokens += len(left_sentence)
        return shared_tokens >= MIN_SHARED_COPY_CONTEXT_TOKENS
    @staticmethod
    def copy_text(content: str | None) -> str | None:
        """Return visible text while retaining sentence boundaries for copy checks."""
        if content is None:
            return None
        visible = HTML_TAG_PATTERN.sub(" ", html.unescape(content))
        normalized = " ".join(visible.split())
        return normalized or None
    @staticmethod
    def dependency_text(content: str | None) -> str | None:
        """Return visible word content for explainable copy comparison."""
        if content is None:
            return None
        visible = HTML_TAG_PATTERN.sub(" ", html.unescape(content))
        tokens = TOKEN_PATTERN.findall(visible.casefold())
        return " ".join(tokens) or None

    def domain_from_url(self, normalized_url: str) -> str:
        hostname = urlsplit(normalized_url).hostname
        if hostname is None:
            raise InvalidSourceUrlError("normalized source URL has no hostname")
        return hostname.casefold()
