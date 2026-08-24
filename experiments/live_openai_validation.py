from __future__ import annotations

import json
import os
from pathlib import Path

from memoria_resolutiva.openai_adapter import OpenAIResponsesAdapter
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService

API_KEY = os.environ["OPENAI_API_KEY"]
MODEL = os.getenv("OPENAI_LIVE_MODEL", "gpt-5.6-luna")
BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")


def main() -> None:
    memory = EnterpriseMemoryService(OrganizationIdentity("live-openai-validation"))
    scope = MemoryScope("live-openai-validation")
    memory.remember(
        scope,
        "live-openai-memory",
        "The validation color is cobalt.",
        ("key", "validation.fact"),
        provenance="live-provider-validation",
    )

    adapter = OpenAIResponsesAdapter(
        api_key=API_KEY,
        model=MODEL,
        base_url=BASE_URL,
    )
    chat = ProductChatService(memory, adapter)
    result = chat.run(
        scope=scope,
        message="Reply with the validation color from memory in one word.",
        mode="memoria",
        memory_keys=["validation.fact"],
    )

    report = {
        "validation": "memoria.ia-live-openai-v1",
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
    Path("benchmark-results/live-openai-v1.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        "utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))

    assert report["provider"] == "openai"
    assert report["memory_hits"] == 1
    assert report["external_calls"] == 1
    assert report["response_nonempty"] is True
    assert report["response_mentions_expected_fact"] is True


if __name__ == "__main__":
    main()
