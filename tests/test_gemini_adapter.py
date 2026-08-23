import httpx
import pytest

from memoria_resolutiva.gemini_adapter import GeminiGenerateContentAdapter, GeminiPricing
from memoria_resolutiva.llm_adapter import LLMAdapterError


def test_gemini_materializes_context_and_reads_usage():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = request.read().decode()
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"parts": [{"text": "The stored plan is Pro."}], "role": "model"}}
                ],
                "usageMetadata": {
                    "promptTokenCount": 21,
                    "candidatesTokenCount": 7,
                    "totalTokenCount": 28,
                },
                "modelVersion": "gemini-test",
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(handler))
    adapter = GeminiGenerateContentAdapter(
        api_key="test-key",
        model="gemini-test",
        client=client,
        pricing=GeminiPricing(input_usd_per_million=1.0, output_usd_per_million=2.0),
    )
    response = adapter.generate(message="What is the plan?", context=["Customer plan is Pro."])

    assert response.text == "The stored plan is Pro."
    assert response.provider == "gemini"
    assert response.model == "gemini-test"
    assert response.usage.input_tokens == 21
    assert response.usage.output_tokens == 7
    assert response.usage.estimated_cost_usd == pytest.approx((21 + 14) / 1_000_000)
    assert captured["headers"]["x-goog-api-key"] == "test-key"
    assert "Customer plan is Pro." in captured["body"]
    assert "What is the plan?" in captured["body"]


def test_gemini_accepts_models_prefix():
    adapter = GeminiGenerateContentAdapter(api_key="x", model="models/gemini-test")
    assert adapter.model_name == "gemini-test"


def test_gemini_provider_failure_is_normalized():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={"error": {"message": "rate limited"}})

    adapter = GeminiGenerateContentAdapter(
        api_key="test-key",
        model="gemini-test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LLMAdapterError):
        adapter.generate(message="hello", context=[])


def test_gemini_missing_text_is_rejected():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"candidates": [], "usageMetadata": {}})

    adapter = GeminiGenerateContentAdapter(
        api_key="test-key",
        model="gemini-test",
        client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    with pytest.raises(LLMAdapterError):
        adapter.generate(message="hello", context=[])
