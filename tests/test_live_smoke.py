import pytest

from scripts.live_smoke import error_summary, summarize_response


def test_smoke_summary_exposes_only_bounded_fields() -> None:
    payload = {
        "analysis_id": "private-debug-id",
        "initial_decision": "BUY",
        "decision": "BUY_IF",
        "confidence": 0.62,
        "counter_evidence_attempted": True,
        "counter_evidence_completed": True,
        "sources": [{"url": "https://example.com/private-source"}],
        "claims": [{"evidence": "long raw evidence must not be printed"}],
    }

    assert summarize_response(200, payload) == {
        "http_status": 200,
        "initial_decision": "BUY",
        "decision": "BUY_IF",
        "confidence": 0.62,
        "counter_attempted": True,
        "counter_completed": True,
        "source_count": 1,
    }


def test_smoke_summary_rejects_incomplete_contract() -> None:
    with pytest.raises(ValueError, match="missing fields"):
        summarize_response(200, {"decision": "BUY"})


def test_smoke_error_summary_exposes_code_without_message() -> None:
    payload = {
        "detail": {
            "code": "MODEL_PROVIDER_UNAVAILABLE",
            "message": "provider response containing internal context",
        }
    }

    assert error_summary(503, payload) == {
        "http_status": 503,
        "error_code": "MODEL_PROVIDER_UNAVAILABLE",
    }
