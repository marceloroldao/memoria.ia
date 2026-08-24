from __future__ import annotations

import argparse
import json
from pathlib import Path

from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService, token_reduction
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService

DATASET = [
    {
        "message": "What plan does customer alpha use?",
        "memories": {
            "customer.alpha.plan": "Customer alpha uses the Pro plan.",
            "customer.alpha.invoice": "Customer alpha invoice 2026-08 is paid.",
            "network.status": "Core network is operating normally.",
        },
        "memory_keys": ["customer.alpha.plan"],
    },
    {
        "message": "What is the invoice status?",
        "memories": {
            "customer.alpha.plan": "Customer alpha uses the Pro plan.",
            "customer.alpha.invoice": "Customer alpha invoice 2026-08 is paid.",
            "network.status": "Core network is operating normally.",
        },
        "memory_keys": ["customer.alpha.invoice"],
    },
    {
        "message": "Is the core network healthy?",
        "memories": {
            "customer.alpha.plan": "Customer alpha uses the Pro plan.",
            "customer.alpha.invoice": "Customer alpha invoice 2026-08 is paid.",
            "network.status": "Core network is operating normally.",
        },
        "memory_keys": ["network.status"],
    },
]


def run_benchmark() -> dict:
    memory = EnterpriseMemoryService(OrganizationIdentity("benchmark-org"))
    scope = MemoryScope("benchmark-org", application_id="benchmark")
    all_context: list[str] = []
    seen: set[str] = set()
    for row in DATASET:
        for key, value in row["memories"].items():
            if key not in seen:
                memory.remember(scope, key, value, ("key", key), provenance="product-benchmark")
                seen.add(key)
                all_context.append(value)

    # Fixed irrelevant context makes the baseline intentionally explicit and
    # reproducible. This benchmark tests selection/instrumentation, not semantic
    # discovery quality and not a real provider tokenizer.
    baseline_context = tuple(all_context + [
        "Historical support transcript not relevant to the current request. " * 8,
        "Repeated operational notes not relevant to the current request. " * 8,
    ])
    chat = ProductChatService(memory, MockLLMAdapter())

    cases = []
    baseline_total = memoria_total = 0
    for index, row in enumerate(DATASET, start=1):
        baseline = chat.run(
            scope=scope,
            message=row["message"],
            mode="baseline",
            baseline_context=baseline_context,
        )
        memoria = chat.run(
            scope=scope,
            message=row["message"],
            mode="memoria",
            memory_keys=row["memory_keys"],
        )
        baseline_total += baseline.metrics.input_tokens
        memoria_total += memoria.metrics.input_tokens
        cases.append({
            "case": index,
            "message": row["message"],
            "baseline_input_tokens": baseline.metrics.input_tokens,
            "memoria_input_tokens": memoria.metrics.input_tokens,
            "memory_hits": memoria.metrics.memory_hits,
            "memory_misses": memoria.metrics.memory_misses,
            "baseline_context_chars": baseline.metrics.context_sent_chars,
            "memoria_context_chars": memoria.metrics.context_sent_chars,
        })

    reduction = token_reduction(
        baseline_tokens=baseline_total,
        memoria_tokens=memoria_total,
    )
    return {
        "benchmark": "memoria.ia-product-context-v1",
        "provider": "mock",
        "token_measurement": "deterministic_char_estimate_not_provider_tokenizer",
        "cases": cases,
        "summary": {
            "case_count": len(cases),
            "baseline_input_tokens": baseline_total,
            "memoria_input_tokens": memoria_total,
            "token_reduction": reduction,
            "token_reduction_percent": None if reduction is None else reduction * 100.0,
            "memory_hits": sum(c["memory_hits"] for c in cases),
            "memory_misses": sum(c["memory_misses"] for c in cases),
        },
        "limitations": [
            "Mock adapter is not an LLM.",
            "Token counts are deterministic estimates, not provider tokenizer counts.",
            "Memory keys are supplied explicitly; this does not benchmark semantic discovery.",
            "No external provider cost saving is claimed from this benchmark.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run_benchmark()
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
