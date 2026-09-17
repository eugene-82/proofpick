import json

import httpx
import pytest

from app.claim_extraction import (
    ClaimOutputValidationError,
    ClaimProviderConfigurationError,
    ClaimProviderError,
    ClaimProviderRateLimitError,
    OpenAIClaimExtractionProvider,
)
from app.evidence_processing import EvidenceDocument, EvidenceSource
from app.source_filtering import SourceType


def evidence() -> EvidenceDocument:
    text = "Battery lasts all day."
    return EvidenceDocument(
        source_key="S001",
        original_url="https://example.com/review",
        normalized_url="https://example.com/review",
        domain="example.com",
        title="Review",
        text=text,
        evidence_source=EvidenceSource.RAW_CONTENT,
        original_length=len(text),
        compressed_length=len(text),
        compression_ratio=1,
        truncated=False,
        source_type=SourceType.WEB,
        independence_group_id="IG001",
    )


def test_openai_provider_uses_json_schema_without_live_network() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert request.url == httpx.URL("https://api.openai.com/v1/responses")
        assert request.headers["authorization"] == "Bearer test-key"
        assert body["model"] == "test-model"
        assert body["store"] is False
        assert body["text"]["format"]["type"] == "json_schema"
        assert body["text"]["format"]["strict"] is True
        schema = body["text"]["format"]["schema"]
        assert schema["additionalProperties"] is False
        assert schema["required"] == ["claims"]
        claim_schema = schema["$defs"]["ExtractedClaim"]
        assert "usage_period_months" in claim_schema["required"]
        assert "semantic_relation" in claim_schema["required"]
        assert claim_schema["required"] == list(claim_schema["properties"])
        assert claim_schema["additionalProperties"] is False
        assert "default" not in claim_schema["properties"]["semantic_relation"]
        semantic_relation = claim_schema["properties"]["semantic_relation"]
        assert {item.get("type") for item in semantic_relation["anyOf"]} == {
            None,
            "null",
        }
        relation_schema = schema["$defs"]["SemanticRelation"]
        assert relation_schema["additionalProperties"] is False
        assert relation_schema["required"] == list(relation_schema["properties"])
        assert "experiencer" in relation_schema["required"]
        assert "observation_months" in relation_schema["required"]
        assert {item.get("type") for item in relation_schema["properties"]["experiencer"]["anyOf"]} == {
            "string",
            "null",
        }
        assert {item.get("type") for item in relation_schema["properties"]["observation_months"]["anyOf"]} == {
            "integer",
            "null",
        }
        assert schema["properties"]["claims"]["items"] == {
            "$ref": "#/$defs/ExtractedClaim"
        }
        request_input = json.loads(body["input"])
        assert request_input["target_product_id"] == "unspecified-product"
        request_evidence = request_input["evidence_documents"][0]
        assert request_evidence["source_id"] == "S001"
        assert request_evidence["evidence_source"] == "raw_content"
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [
                            {"type": "output_text", "text": json.dumps({"claims": []})}
                        ],
                    }
                ]
            },
        )

    provider = OpenAIClaimExtractionProvider(
        api_key="test-key",
        model="test-model",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )

    assert provider.extract_batch([evidence()]) == {"claims": []}


@pytest.mark.parametrize(
    ("status_code", "error_type"),
    [
        (429, ClaimProviderRateLimitError),
        (500, ClaimProviderError),
    ],
)
def test_openai_provider_maps_http_failures(
    status_code: int, error_type: type[Exception]
) -> None:
    provider = OpenAIClaimExtractionProvider(
        api_key="test-key",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(status_code, json={"error": "failed"})
            )
        ),
    )

    with pytest.raises(error_type):
        provider.extract_batch([evidence()])


def test_openai_provider_rejects_malformed_output_text() -> None:
    provider = OpenAIClaimExtractionProvider(
        api_key="test-key",
        client=httpx.Client(
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"output": []})
            )
        ),
    )

    with pytest.raises(ClaimOutputValidationError):
        provider.extract_batch([evidence()])


def test_openai_provider_requires_an_api_key() -> None:
    with pytest.raises(ClaimProviderConfigurationError):
        OpenAIClaimExtractionProvider(api_key=" ")
