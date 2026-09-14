"""Conservative text cleaning for extractive evidence."""

import re
from html.parser import HTMLParser


HTML_TAG_PATTERN = re.compile(r"</?[a-zA-Z][^>]*>")
BLOCK_TAGS = frozenset(
    {
        "article",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "main",
        "p",
        "section",
    }
)
SKIPPED_TAGS = frozenset({"noscript", "script", "style", "template"})
BOILERPLATE_LINES = frozenset(
    {
        "accept cookies",
        "cookie settings",
        "log in",
        "privacy policy",
        "share",
        "sign in",
        "sign up",
        "terms of service",
    }
)


class _HtmlTextExtractor(HTMLParser):
    """Small stdlib HTML-to-text adapter for provider-supplied raw content."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag in SKIPPED_TAGS:
            self._skip_depth += 1
        elif self._skip_depth == 0 and tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in SKIPPED_TAGS and self._skip_depth:
            self._skip_depth -= 1
        elif self._skip_depth == 0 and tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            self.parts.append(data)


class EvidenceCleaner:
    """Normalize text while retaining meaningful wording and paragraph boundaries."""

    def clean(self, text: str) -> str:
        text = self._html_to_text_if_needed(text)
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        text = "".join(character if character >= " " or character == "\n" else " " for character in text)
        lines = [re.sub(r"[ \t\f\v]+", " ", line).strip() for line in text.split("\n")]
        normalized = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()

        paragraphs = [paragraph.strip() for paragraph in normalized.split("\n\n") if paragraph.strip()]
        unique_paragraphs: list[str] = []
        seen: set[str] = set()
        for paragraph in paragraphs:
            if self._is_boilerplate(paragraph) or paragraph in seen:
                continue
            seen.add(paragraph)
            unique_paragraphs.append(paragraph)
        return "\n\n".join(unique_paragraphs)

    @staticmethod
    def _html_to_text_if_needed(text: str) -> str:
        if not HTML_TAG_PATTERN.search(text):
            return text
        parser = _HtmlTextExtractor()
        parser.feed(text)
        parser.close()
        return "".join(parser.parts)

    @staticmethod
    def _is_boilerplate(paragraph: str) -> bool:
        normalized = paragraph.casefold()
        return (
            normalized in BOILERPLATE_LINES
            or normalized.startswith("copyright ")
            or normalized.startswith("©")
        )
