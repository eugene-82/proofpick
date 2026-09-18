import pytest

from app.product_resolution import SearchAssistedIdentityResolver
from app.search.models import SearchResult


def result(index: int, title: str, text: str | None = None) -> SearchResult:
    return SearchResult(
        title=title,
        url=f"https://review-{index}.example.com/product",
        snippet=text or title,
        raw_content=text,
    )


@pytest.mark.parametrize(
    ("query", "brand", "model_terms"),
    [
        ("Sony WH-1000XM5", "Sony", ("wh1000xm5",)),
        ("Logitech MX Master 3S", "Logitech", ("mx", "3s")),
        ("Dyson V15 Detect", "Dyson", ("v15",)),
        ("Nintendo Switch OLED", "Nintendo", ("oled",)),
    ],
)
def test_clear_model_like_input_becomes_provisional_candidate(
    query: str, brand: str, model_terms: tuple[str, ...]
) -> None:
    candidate = SearchAssistedIdentityResolver().provisional_candidate(query)

    assert candidate is not None
    assert candidate.brand == brand
    assert candidate.canonical_name == query
    assert candidate.model_terms == model_terms


@pytest.mark.parametrize(
    "query",
    ["headphones", "mouse", "dyson", "samsung", "best earbuds"],
)
def test_generic_input_does_not_become_provisional(query: str) -> None:
    assert SearchAssistedIdentityResolver().provisional_candidate(query) is None


def test_lowercase_words_plus_only_a_year_do_not_become_a_candidate() -> None:
    assert (
        SearchAssistedIdentityResolver().provisional_candidate(
            "mysterious gadget 42"
        )
        is None
    )


def test_multiple_distinct_exact_results_confirm_identity() -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate("Acme ZX-500 Pro")
    assert candidate is not None

    confirmed = resolver.confirm(
        candidate,
        [
            result(1, "Acme ZX-500 Pro long-term review"),
            result(2, "Testing the Acme ZX-500 Pro"),
            result(3, "Acme ZX-500 accessories"),
        ],
    )

    assert confirmed is not None
    assert confirmed.ambiguous is False
    assert confirmed.canonical_name == "Acme ZX-500 Pro"
    assert confirmed.model == "ZX-500"


@pytest.mark.parametrize(
    "query",
    [
        "Sony WH-1000XM5",
        "Logitech MX Master 3S",
        "Dyson V15 Detect",
        "Nintendo Switch OLED",
    ],
)
def test_explicit_demo_shapes_confirm_with_multiple_exact_results(query: str) -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate(query)
    assert candidate is not None

    confirmed = resolver.confirm(
        candidate,
        [
            result(1, f"{query} long-term review"),
            result(2, f"Testing {query} after six months"),
            result(3, f"{candidate.brand} product comparison"),
        ],
    )

    assert confirmed is not None
    assert confirmed.canonical_name == query


@pytest.mark.parametrize(
    ("query", "titles"),
    [
        (
            "Sony WH-1000XM5",
            ["Sony WH-1000XM5 review", "Sony WH-1000XM4 review", "Sony headphones"],
        ),
        (
            "Apple AirPods Pro 2",
            ["Apple AirPods Pro 2 review", "Apple AirPods Pro review", "AirPods Pro guide"],
        ),
        (
            "Nintendo Switch OLED",
            ["Nintendo Switch OLED review", "Nintendo Switch review", "Nintendo Switch guide"],
        ),
    ],
)
def test_one_exact_result_among_competing_variants_is_not_confirmed(
    query: str, titles: list[str]
) -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate(query)
    assert candidate is not None

    confirmed = resolver.confirm(
        candidate,
        [result(index, title) for index, title in enumerate(titles, start=1)],
    )

    assert confirmed is None


def test_repeated_results_from_one_domain_do_not_count_as_multiple_support() -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate("Acme ZX-500")
    assert candidate is not None
    results = [
        SearchResult(
            title="Acme ZX-500 review",
            url=f"https://same.example.com/review/{index}",
            snippet="Acme ZX-500 review",
        )
        for index in range(3)
    ]

    assert resolver.confirm(candidate, results) is None


def test_only_exact_model_results_are_returned_for_downstream_use() -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate("Acme ZX-500")
    assert candidate is not None
    exact = result(1, "Acme ZX-500 review")
    competing = result(2, "Acme ZX-400 review")

    assert resolver.supporting_results(candidate, [exact, competing]) == [exact]


def test_downstream_filter_is_not_limited_to_confirmation_window() -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate("Acme ZX-500")
    assert candidate is not None
    exact_results = [
        result(index, "Acme ZX-500 review") for index in range(1, 8)
    ]

    assert resolver.supporting_results(candidate, exact_results) == exact_results


def test_downstream_filter_retains_brand_omitted_exact_model_review() -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate("Logitech MX Master 3S")
    assert candidate is not None
    review = result(
        1,
        "MX Master 3S Review",
        "After six months, my Logitech MX Master 3S still tracks reliably.",
    )

    assert resolver.supporting_results(candidate, [review]) == [review]


def test_downstream_filter_can_confirm_exact_identity_in_body() -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate("Logitech MX Master 3S")
    assert candidate is not None
    community_post = result(
        1,
        "Six months later: an owner update",
        "I have used the Logitech MX Master 3S daily for six months.",
    )

    assert resolver.supporting_results(candidate, [community_post]) == [
        community_post
    ]


def test_brand_omitted_surface_rejects_explicit_competing_brand() -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate("Logitech MX Master 3S")
    assert candidate is not None
    wrong_brand = result(
        1,
        "MX Master 3S Review",
        "This Acme MX Master 3S mouse was tested for six months.",
    )

    assert resolver.supporting_results(candidate, [wrong_brand]) == []


@pytest.mark.parametrize(
    ("query", "competing_title", "competing_body"),
    [
        (
            "Sony WH-1000XM5",
            "Sony WH-1000XM4 long-term review",
            "The Sony WH-1000XM4 was tested for a year.",
        ),
        (
            "Apple AirPods Pro 2",
            "AirPods Pro long-term review",
            "The Apple AirPods Pro was tested for a year.",
        ),
        (
            "Nintendo Switch OLED",
            "Nintendo Switch long-term review",
            "The Nintendo Switch was tested for a year.",
        ),
    ],
)
def test_downstream_filter_rejects_generation_or_variant_mismatch(
    query: str, competing_title: str, competing_body: str
) -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate(query)
    assert candidate is not None

    assert resolver.supporting_results(
        candidate, [result(1, competing_title, competing_body)]
    ) == []


def test_generic_category_page_is_not_promoted_by_body_mention() -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate("Logitech MX Master 3S")
    assert candidate is not None
    category_page = result(
        1,
        "Best wireless mouse picks",
        "Our list includes the Logitech MX Master 3S among many products.",
    )

    assert resolver.supporting_results(candidate, [category_page]) == []


def test_mx_like_result_set_retains_reviews_and_rejects_competing_results() -> None:
    resolver = SearchAssistedIdentityResolver()
    candidate = resolver.provisional_candidate("Logitech MX Master 3S")
    assert candidate is not None
    retained_reviews = [
        result(
            index,
            (
                "Logitech MX Master 3S owner review"
                if index <= 4
                else "MX Master 3S long-term review"
            ),
            "I used the Logitech MX Master 3S daily for six months.",
        )
        for index in range(1, 9)
    ]
    rejected_results = [
        result(9, "Logitech MX Master 2S review"),
        result(10, "Logitech MX Master 3 review"),
        result(11, "Acme MX Master 3S review", "Acme MX Master 3S mouse."),
        result(
            12,
            "Best wireless mouse picks",
            "The Logitech MX Master 3S appears in this product roundup.",
        ),
        result(13, "Logitech MX Master 3S vs MX Master 3"),
        result(14, "Mouse accessories and replacement parts"),
        result(15, "Logitech MX Keys keyboard review"),
    ]
    raw_results = [*retained_reviews, *rejected_results]

    assert len(raw_results) == 15
    assert resolver.supporting_results(candidate, raw_results) == retained_reviews
