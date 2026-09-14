"""Minimal OpenAI Responses API provider for structured claim output."""

import json
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


DEFAULT_OPENAI_CLAIM_MODEL = "gpt-4.1-mini"
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"


class OpenAIClaimExtractionProvider(ClaimExtractionProvider):
    """Call OpenAI Structured Outputs without coupling extraction to an SDK."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_OPENAI_CLAIM_MODEL,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        if not api_key.strip():
            raise ClaimProviderConfigurationError("OPENAI_API_KEY is required")
        if not model.strip():
            raise ClaimProviderConfigurationError("OPENAI_CLAIM_MODEL is required")
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=timeout_seconds)

    @classmethod
    def from_env(cls) -> "OpenAIClaimExtractionProvider":
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            model=os.getenv("OPENAI_CLAIM_MODEL", DEFAULT_OPENAI_CLAIM_MODEL),
        )

    def extract_batch(
        self,
        documents: Sequence[EvidenceDocument],
        *,
        repair: bool = False,
    ) -> Any:
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
        request_body = {
            "model": self._model,
            "instructions": instructions,
            "input": json.dumps({"evidence_documents": evidence}, ensure_ascii=False),
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "proofpick_claim_extraction",
                    "strict": True,
                    "schema": ClaimExtractionPayload.model_json_schema(),
                }
            },
            "store": False,
        }

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

    @staticmethod
    def _output_text(response_data: dict[str, Any]) -> str:
        for item in response_data.get("output", []):
            if item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if content.get("type") == "output_text":
                    return content["text"]
        raise ClaimOutputValidationError("OpenAI response did not include structured output text")
