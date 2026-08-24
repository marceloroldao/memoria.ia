import json

import httpx
import pytest

from memoria_resolutiva.llm_adapter import LLMAdapterError
from memoria_resolutiva.openai_adapter import OpenAIPricing, OpenAIResponsesAdapter


def test_openai_adapter_materializes_context_and_reads_provider_usage():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["authorization"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(
            200,
            json={
                "output": [
                    {
                        "type": "message",
                        "content": [{"type": "output_text", "text": "answer"}],
                    }
                ],
                "usage": {"input_tokens": 100, "output_tokens": 20},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = OpenAIResponsesAdapter(
        api_key="test-key",
        model="test-model",
        client=client,
        pricing=OpenAIPricing(input_usd_per_million=2.0, output_usd_per_million=10.0),
    )
    result = adapter.generate(message="question", context=["selected memory"])

    assert captured["authorization"] == "Bearer test-key"
    assert captured["body"]["model"] == "test-model"
    assert "selected memory" in captured["body"]["input"]
    assert "question" in captured["body"]["input"]
    assert result.text == "answer"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 20
    assert result.usage.estimated_cost_usd == pytest.approx(0.0004)


def test_openai_adapter_does_not_claim_cost_without_configured_pricing():
    client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "output": [{"type": "message", "content": [{"type": "output_text", "text": "ok"}]}],
                    "usage": {"input_tokens": 5, "output_tokens": 2},
                },
            )
        )
    )
    adapter = OpenAIResponsesAdapter(api_key="test", model="model", client=client)
    assert adapter.generate(message="q", context=[]).usage.estimated_cost_usd is None


def test_openai_adapter_maps_provider_failure_to_neutral_error():
    client = httpx.Client(
        transport=httpx.MockTransport(lambda request: httpx.Response(503, json={"error": "unavailable"}))
    )
    adapter = OpenAIResponsesAdapter(api_key="test", model="model", client=client)
    with pytest.raises(LLMAdapterError):
        adapter.generate(message="q", context=[])
