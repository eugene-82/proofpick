from app.evidence_processing import (
    DeterministicEvidenceProcessor,
    EvidenceBudgetPolicy,
    EvidenceCleaner,
    EvidenceSource,
)
from app.source_filtering import FilteredSource, SourceNormalizer, SourceType


def source(
    *,
    source_key: str = "S003",
    raw_content: str | None = None,
    snippet: str | None = "Snippet evidence.",
    title: str | None = "Source title",
) -> FilteredSource:
    original_url = "https://example.com/review"
    return FilteredSource(
        source_key=source_key,
        original_url=original_url,
        normalized_url=original_url,
        domain="example.com",
        title=title,
        snippet=snippet,
        raw_content=raw_content,
        source_type=SourceType.WEB,
        content_hash=SourceNormalizer().content_fingerprint(raw_content or snippet),
        independence_group_id="IG003",
    )


def test_raw_content_is_preferred_over_snippet() -> None:
    document = DeterministicEvidenceProcessor().process(
        source(raw_content="Raw evidence is retained.", snippet="Snippet must not be used.")
    )

    assert document is not None
    assert document.text == "Raw evidence is retained."
    assert document.evidence_source is EvidenceSource.RAW_CONTENT


def test_snippet_is_used_when_raw_content_is_missing() -> None:
    document = DeterministicEvidenceProcessor().process(source(raw_content=None, snippet="Fallback evidence."))

    assert document is not None
    assert document.text == "Fallback evidence."
    assert document.evidence_source is EvidenceSource.SNIPPET


def test_cleaner_normalizes_whitespace_line_endings_and_blank_lines() -> None:
    cleaned = EvidenceCleaner().clean("  First  line.\r\n\r\n\r\n Second\t line. \r Third line.  ")

    assert cleaned == "First line.\n\nSecond line.\nThird line."


def test_cleaner_removes_exact_repeated_paragraph_and_conservative_boilerplate() -> None:
    cleaned = EvidenceCleaner().clean(
        "Actual review paragraph.\n\nAccept cookies\n\nActual review paragraph.\n\nPrivacy policy"
    )

    assert cleaned == "Actual review paragraph."


def test_html_cleaning_discards_script_and_retains_visible_text() -> None:
    cleaned = EvidenceCleaner().clean(
        "<article><p>6개월 후 배터리 50% 수준</p><script>ignore()</script><p>실사용 후기</p></article>"
    )

    assert "6개월 후 배터리 50% 수준" in cleaned
    assert "실사용 후기" in cleaned
    assert "ignore()" not in cleaned


def test_korean_numbers_units_emoji_and_model_name_are_preserved() -> None:
    text = "로보락 Q Revo는 6개월 후 배터리가 50% 수준이었습니다. 👍"
    document = DeterministicEvidenceProcessor().process(source(raw_content=text))

    assert document is not None
    assert document.text == text


def test_short_evidence_is_not_truncated_and_metrics_are_measured() -> None:
    text = "Battery lasts 8 hours."
    document = DeterministicEvidenceProcessor().process(source(raw_content=text))

    assert document is not None
    assert document.original_length == len(text)
    assert document.compressed_length == len(text)
    assert document.compression_ratio == 1
    assert document.truncated is False


def test_long_evidence_is_bounded_and_keeps_beginning_middle_and_end() -> None:
    long_text = (
        f"FRONT: introduction {'a' * 120}\n\n"
        f"MIDDLE: after six months {'b' * 120}\n\n"
        f"{'c' * 120} TAIL: battery declined after long-term use"
    )
    processor = DeterministicEvidenceProcessor(EvidenceBudgetPolicy(max_chars_per_source=120))

    document = processor.process(source(raw_content=long_text))

    assert document is not None
    assert document.compressed_length <= 120
    assert document.truncated is True
    assert "FRONT:" in document.text
    assert "MIDDLE: after six months" in document.text
    assert "battery declined after long-term use" in document.text


def test_compression_metrics_reflect_cleaning_and_bounding() -> None:
    text = f"Start {'a' * 300}\n\nMiddle {'b' * 300}\n\n{'c' * 300} End"
    document = DeterministicEvidenceProcessor(EvidenceBudgetPolicy(max_chars_per_source=150)).process(
        source(raw_content=text)
    )

    assert document is not None
    assert document.original_length == len(text)
    assert document.compressed_length == len(document.text)
    assert 0 < document.compression_ratio < 1


def test_source_provenance_and_fingerprint_are_preserved() -> None:
    input_source = source(source_key="S017", raw_content="Evidence.", title="Review title")
    document = DeterministicEvidenceProcessor().process(input_source)

    assert document is not None
    assert document.source_key == "S017"
    assert document.original_url == input_source.original_url
    assert document.normalized_url == input_source.normalized_url
    assert document.domain == input_source.domain
    assert document.content_hash == input_source.content_hash
    assert document.independence_group_id == input_source.independence_group_id


def test_empty_raw_and_snippet_are_defensively_skipped() -> None:
    document = DeterministicEvidenceProcessor().process(
        source(raw_content="  ", snippet="  ", title="A title without evidence")
    )

    assert document is None


def test_processing_is_deterministic_and_process_all_preserves_order() -> None:
    processor = DeterministicEvidenceProcessor()
    inputs = [
        source(source_key="S001", raw_content="First evidence."),
        source(source_key="S002", raw_content=None, snippet=None),
        source(source_key="S003", raw_content="Third evidence."),
    ]

    first = processor.process(inputs[0])
    second = processor.process(inputs[0])
    all_documents = processor.process_all(inputs)

    assert first == second
    assert [document.source_key for document in all_documents] == ["S001", "S003"]
