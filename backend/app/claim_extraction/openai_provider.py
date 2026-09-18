"""Minimal OpenAI Responses API provider for structured claim output."""

import json
import math
import os
from collections.abc import Sequence
from typing import Any

import httpx

from app.evidence_processing.models import EvidenceDocument

from .base import ClaimExtractionProvider
from .exceptions import (
    ClaimOutputValidationError,
    ClaimProviderConfigurationError,
    ClaimProviderError,
    ClaimProviderRateLimitError,
    ClaimProviderTimeoutError,
)
from .models import ClaimExtractionPayload
from .prompts import CLAIM_EXTRACTION_INSTRUCTIONS, REPAIR_INSTRUCTION
from .schema import strict_model_json_schema


DEFAULT_OPENAI_CLAIM_MODEL = "gpt-4.1-mini"
DEFAULT_OPENAI_EXTRACTION_TIMEOUT_SECONDS = 90.0
MAX_OPENAI_EXTRACTION_TIMEOUT_SECONDS = 300.0
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAIClaimExtractionProvider(ClaimExtractionProvider):
    """Call OpenAI Structured Outputs without coupling extraction to an SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_CLAIM_MODEL,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = DEFAULT_OPENAI_EXTRACTION_TIMEOUT_SECONDS,
    ) -> None:
        if not api_key.strip():
            raise ClaimProviderConfigurationError("OPENAI_API_KEY is required")
        if not model.strip():
            raise ClaimProviderConfigurationError("OPENAI_CLAIM_MODEL is required")
        if (
            not math.isfinite(timeout_seconds)
            or timeout_seconds <= 0
            or timeout_seconds > MAX_OPENAI_EXTRACTION_TIMEOUT_SECONDS
        ):
            raise ClaimProviderConfigurationError(
                "OPENAI_EXTRACTION_TIMEOUT_SECONDS must be greater than 0 "
                f"and at most {MAX_OPENAI_EXTRACTION_TIMEOUT_SECONDS:g}"
            )
        self._api_key = api_key
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._client = client or httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_env(cls) -> "OpenAIClaimExtractionProvider":
        timeout_value = os.getenv(
            "OPENAI_EXTRACTION_TIMEOUT_SECONDS",
            str(DEFAULT_OPENAI_EXTRACTION_TIMEOUT_SECONDS),
        )
        try:
            timeout_seconds = float(timeout_value)
        except ValueError as error:
            raise ClaimProviderConfigurationError(
                "OPENAI_EXTRACTION_TIMEOUT_SECONDS must be numeric"
            ) from error
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_CLAIM_MODEL", DEFAULT_OPENAI_CLAIM_MODEL),
            timeout_seconds=timeout_seconds,
        )

    def extract_batch(
        self,
        documents: Sequence[EvidenceDocument],
        *,
        repair: bool = False,
        target_product_id: str = "unspecified-product",
    ) -> Any:
        request_body = self.build_request_body(
            documents,
            repair=repair,
            target_product_id=target_product_id,
        )

        try:
            response = self._client.post(
                OPENAI_RESPONSES_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=request_body,
            )
        except httpx.TimeoutException as error:
            raise ClaimProviderTimeoutError("OpenAI claim extraction timed out") from error
        except httpx.RequestError as error:
            raise ClaimProviderError("OpenAI claim extraction request failed") from error

        if response.status_code == 429:
            raise ClaimProviderRateLimitError("OpenAI claim extraction rate limit reached")
        if response.is_error:
            raise ClaimProviderError(
                f"OpenAI claim extraction failed with HTTP {response.status_code}"
            )

        try:
            response_data = response.json()
            output_text = self._output_text(response_data)
            return json.loads(output_text)
        except (TypeError, ValueError, KeyError) as error:
            raise ClaimOutputValidationError(
                "OpenAI claim extraction returned malformed structured output"
            ) from error

    def build_request_body(
        self,
        documents: Sequence[EvidenceDocument],
        *,
        repair: bool = False,
        target_product_id: str = "unspecified-product",
    ) -> dict[str, Any]:
        """Build the exact strict request payload without performing I/O."""

        evidence = [
            {
                "source_id": document.source_key,
                "title": document.title,
                "domain": document.domain,
                "evidence_source": document.evidence_source.value,
                "text": document.text,
            }
            for document in documents
        ]
        instructions = CLAIM_EXTRACTION_INSTRUCTIONS
        if repair:
            instructions = f"{instructions}\n\n{REPAIR_INSTRUCTION}"
        return {
            "model": self._model,
            "instructions": instructions,
            "input": json.dumps(
                {
                    "target_product_id": target_product_id,
                    "evidence_documents": evidence,
                },
                ensure_ascii=False,
            ),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "proofpick_claim_extraction",
                    "strict": True,
                    "schema": strict_model_json_schema(ClaimExtractionPayload),
                }
            },
            "store": False,
        }

    @staticmethod
    def _output_text(response_data: dict[str, Any]) -> str:
        for item in response_data.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content["text"]
        raise ClaimOutputValidationError("OpenAI response did not include structured output text")
