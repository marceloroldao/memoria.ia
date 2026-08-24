from __future__ import annotations

import json
import os
from pathlib import Path

import httpx

from memoria_resolutiva.gemini_adapter import GeminiGenerateContentAdapter
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService

BASE_URL = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta").rstrip("/")
API_KEY = os.environ["GEMINI_API_KEY"]


def choose_model(client: httpx.Client) -> str:
    response = client.get(
        f"{BASE_URL}/models",
        headers={"x-goog-api-key": API_KEY},
    )
    response.raise_for_status()
    models = response.json().get("models", [])
    candidates = []
    for model in models:
        name = model.get("name", "")
        methods = model.get("supportedGenerationMethods") or model.get("supportedActions") or []
        if "generateContent" not in methods:
            continue
        short = name.removeprefix("models/")
        if "flash" in short.lower():
            candidates.append(short)
    if not candidates:
        raise RuntimeError("no Gemini Flash model supporting generateContent is available for this key")

    def rank(name: str) -> tuple[int, str]:
        lowered = name.lower()
        preview_penalty = 1 if ("preview" in lowered or "exp" in lowered) else 0
        return (preview_penalty, lowered)

    return sorted(candidates, key=rank)[0]


def main() -> None:
    client = httpx.Client(timeout=60.0)
    model = choose_model(client)

    memory = EnterpriseMemoryService(OrganizationIdentity("live-gemini-validation"))
    scope = MemoryScope("live-gemini-validation")
    memory.remember(
        scope,
        "live-gemini-memory",
        "The validation color is cobalt.",
        ("key", "validation.fact"),
        provenance="live-provider-validation",
    )

    adapter = GeminiGenerateContentAdapter(
        api_key=API_KEY,
        model=model,
        base_url=BASE_URL,
        client=client,
    )
    chat = ProductChatService(memory, adapter)
    result = chat.run(
        scope=scope,
        message="Reply with the validation color from memory in one word.",
        mode="memoria",
        memory_keys=["validation.fact"],
    )

    report = {
        "validation": "memoria.ia-live-gemini-v1",
        "provider": result.metrics.provider,
        "model": result.metrics.model,
        "memory_hits": result.metrics.memory_hits,
        "memory_misses": result.metrics.memory_misses,
        "retrieved_context_chars": result.metrics.retrieved_context_chars,
        "context_sent_chars": result.metrics.context_sent_chars,
        "input_tokens": result.metrics.input_tokens,
        "output_tokens": result.metrics.output_tokens,
        "memory_latency_ms": result.metrics.memory_latency_ms,
        "llm_latency_ms": result.metrics.llm_latency_ms,
        "external_calls": result.metrics.external_calls,
        "response_nonempty": bool(result.text.strip()),
        "response_mentions_expected_fact": "cobalt" in result.text.lower(),
        "secret_recorded": False,
    }

    Path("benchmark-results").mkdir(exist_ok=True)
    Path("benchmark-results/live-gemini-v1.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        "utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))

    assert report["provider"] == "gemini"
    assert report["memory_hits"] == 1
    assert report["external_calls"] == 1
    assert report["response_nonempty"] is True
    assert report["response_mentions_expected_fact"] is True


if __name__ == "__main__":
    main()
