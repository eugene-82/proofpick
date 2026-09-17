"""Submit one live ProofPick analysis and print only bounded summary fields."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def summarize_response(status: int, payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("analysis response must be a JSON object")
    required = {
        "decision",
        "confidence",
        "initial_decision",
        "counter_evidence_attempted",
        "counter_evidence_completed",
        "sources",
    }
    missing = sorted(required.difference(payload))
    if missing:
        raise ValueError(f"analysis response is missing fields: {', '.join(missing)}")
    sources = payload["sources"]
    if not isinstance(sources, list):
        raise ValueError("analysis response sources must be a list")
    return {
        "http_status": status,
        "initial_decision": payload["initial_decision"],
        "decision": payload["decision"],
        "confidence": payload["confidence"],
        "counter_attempted": payload["counter_evidence_attempted"],
        "counter_completed": payload["counter_evidence_completed"],
        "source_count": len(sources),
    }


def error_summary(status: int, payload: object) -> dict[str, Any]:
    code = "UNKNOWN_ERROR"
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, dict) and isinstance(detail.get("code"), str):
            code = detail["code"]
    return {"http_status": status, "error_code": code}


def _read_json(response: Any) -> object:
    return json.loads(response.read().decode("utf-8"))


def run(base_url: str, query: str, timeout_seconds: float) -> int:
    endpoint = f"{base_url.rstrip('/')}/api/analyses"
    request = Request(
        endpoint,
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            output = summarize_response(response.status, _read_json(response))
    except HTTPError as error:
        try:
            payload = _read_json(error)
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        print(json.dumps(error_summary(error.code, payload), ensure_ascii=False))
        return 1
    except (TimeoutError, URLError) as error:
        print(
            json.dumps(
                {"http_status": None, "error_code": type(error).__name__},
                ensure_ascii=False,
            )
        )
        return 1
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(json.dumps({"http_status": None, "error_code": str(error)}))
        return 1
    print(json.dumps(output, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="Product name or product URL to analyze")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="ProofPick backend URL (default: %(default)s)",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=300,
        help="Request timeout in seconds (default: %(default)s)",
    )
    args = parser.parse_args()
    if args.timeout <= 0:
        parser.error("--timeout must be greater than zero")
    return run(args.base_url, args.query, args.timeout)


if __name__ == "__main__":
    sys.exit(main())
