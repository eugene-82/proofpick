import pytest

from app.search import SearchResult
from app.source_filtering import (
    DeterministicSourceFilter,
    DropReason,
    InvalidSourceUrlError,
    SourceCandidate,
    SourceNormalizer,
    SourceType,
)


def candidate(
    url: str | None,
    *,
    title: str | None = "Review",
    snippet: str | None = "Useful product experience.",
    raw_content: str | None = None,
) -> SourceCandidate:
    return SourceCandidate(
        url=url,
        title=title,
        snippet=snippet,
        raw_content=raw_content,
    )


def test_url_normalization_removes_tracking_fragment_and_normalizes_host() -> None:
    normalized = SourceNormalizer().normalize_url(
        "HTTPS://WWW.Example.COM:443/post/?id=123&utm_source=google"
        "&utm_medium=cpc#comments"
    )

    assert normalized == "https://example.com/post?id=123"


def test_url_normalization_preserves_identity_query_parameters() -> None:
    normalizer = SourceNormalizer()

    assert normalizer.normalize_url("https://example.com/post?sort=new&id=123") == (
        "https://example.com/post?id=123&sort=new"
    )
    assert normalizer.normalize_url("http://example.com:80/post/") == "http://example.com/post"


@pytest.mark.parametrize(
    "url",
    [None, "", "not-a-url", "ftp://example.com/file", "https://exa mple.com/post"],
)
def test_invalid_url_is_rejected_by_normalizer(url: str | None) -> None:
    with pytest.raises(InvalidSourceUrlError):
        SourceNormalizer().normalize_url(url)


def test_content_fingerprint_normalizes_whitespace_and_is_stable() -> None:
    normalizer = SourceNormalizer()

    first = normalizer.content_fingerprint("  Battery\r\n lasts   all day. ")
    second = normalizer.content_fingerprint("Battery lasts all day.")

    assert first == second
    assert first is not None
    assert len(first) == 64


def test_different_content_has_different_hash_and_missing_content_has_none() -> None:
    normalizer = SourceNormalizer()

    assert normalizer.content_fingerprint("Battery lasts.") != normalizer.content_fingerprint(
        "Battery fails."
    )
    assert normalizer.content_fingerprint(None) is None
    assert normalizer.content_fingerprint("  \r\n ") is None


def test_normalized_url_duplicate_keeps_first_source_and_drop_reason() -> None:
    result = DeterministicSourceFilter().filter(
        [
            candidate("https://example.com/post?id=123&utm_source=search"),
            candidate("https://www.example.com/post/?id=123#comments"),
        ]
    )

    assert [source.source_key for source in result.accepted_sources] == ["S001"]
    assert len(result.dropped_sources) == 1
    dropped = result.dropped_sources[0]
    assert dropped.source_key == "S002"
    assert dropped.reason is DropReason.DUPLICATE_URL
    assert dropped.duplicate_of == "S001"
    assert dropped.independence_group_id == result.accepted_sources[0].independence_group_id


def test_raw_content_duplicate_uses_same_independence_group() -> None:
    result = DeterministicSourceFilter().filter(
        [
            candidate(
                "https://publisher-a.example/review",
                raw_content="Long-term battery performance declined.",
            ),
            candidate(
                "https://publisher-b.example/syndicated-review",
                raw_content=" Long-term   battery performance\r\ndeclined. ",
            ),
        ]
    )

    assert len(result.accepted_sources) == 1
    dropped = result.dropped_sources[0]
    assert dropped.reason is DropReason.DUPLICATE_CONTENT
    assert dropped.duplicate_of == "S001"
    assert dropped.independence_group_id == "IG001"


def test_same_domain_different_posts_are_independent_and_ordered() -> None:
    result = DeterministicSourceFilter().filter(
        [
            candidate("https://reddit.com/r/products/comments/one", snippet="First owner's report."),
            candidate("https://reddit.com/r/products/comments/two", snippet="Second owner's report."),
        ]
    )

    assert [source.source_key for source in result.accepted_sources] == ["S001", "S002"]
    assert [source.independence_group_id for source in result.accepted_sources] == [
        "IG001",
        "IG002",
    ]
    assert all(source.domain == "reddit.com" for source in result.accepted_sources)
    assert all(source.source_type is SourceType.COMMUNITY for source in result.accepted_sources)
    assert result.dropped_sources == []


def test_invalid_and_completely_empty_results_are_traceable_drops() -> None:
    result = DeterministicSourceFilter().filter(
        [
            candidate("not-a-url"),
            candidate("https://example.com/empty", title=None, snippet=None, raw_content=None),
            candidate("https://example.com/title-only", title="Title", snippet=None),
        ]
    )

    assert [source.source_key for source in result.accepted_sources] == ["S001"]
    assert [source.reason for source in result.dropped_sources] == [
        DropReason.INVALID_URL,
        DropReason.EMPTY_CONTENT,
    ]


def test_input_order_is_preserved_after_mixed_drops() -> None:
    result = DeterministicSourceFilter().filter(
        [
            candidate("https://example.com/first", snippet="First unique content."),
            candidate("invalid"),
            candidate("https://example.com/second", snippet="Second unique content."),
            candidate("https://example.com/first?utm_campaign=repeat", snippet="Duplicate URL."),
        ]
    )

    assert [source.source_key for source in result.accepted_sources] == ["S001", "S002"]
    assert [source.source_key for source in result.dropped_sources] == ["S002", "S004"]


def test_contentless_titled_source_is_accepted_without_forced_hash() -> None:
    result = DeterministicSourceFilter().filter(
        [candidate("https://example.com/title-only", title="Useful title", snippet=None)]
    )

    assert len(result.accepted_sources) == 1
    assert result.accepted_sources[0].content_hash is None


def test_search_result_is_supported_without_losing_provenance() -> None:
    search_result = SearchResult(
        url="https://www.Example.com/review?utm_term=product",
        title="Independent review",
        snippet="Tested for six months.",
    )

    result = DeterministicSourceFilter().filter([search_result])

    assert result.accepted_sources[0].original_url == str(search_result.url)
    assert result.accepted_sources[0].normalized_url == "https://example.com/review"
    assert result.accepted_sources[0].snippet == search_result.snippet
