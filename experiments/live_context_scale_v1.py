from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import httpx

from memoria_resolutiva.gemini_adapter import GeminiGenerateContentAdapter
from memoria_resolutiva.openai_adapter import OpenAIResponsesAdapter
from memoria_resolutiva.product_chat import ProductChatService, token_reduction
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService

FACT_KEY = "validation.fact"
FACT_TEXT = "The validation color is cobalt."
QUESTION = "Reply with the validation color from the supplied context in exactly one word."
DEFAULT_SIZES = (1000, 5000, 10000, 50000)


def make_baseline_context(target_tokens: int) -> str:
    # ProductChatService reports provider token counts when available. This
    # generator only targets an approximate scale before the live call; the
    # report records the provider's actual input-token count.
    target_chars = target_tokens * 4
    seed = (
        "Historical support note: routine operations normal; no relation to the "
        "validation color. Sequence {index:06d}. "
    )
    chunks = [FACT_TEXT]
    index = 0
    while sum(len(item) + 1 for item in chunks) < target_chars:
        chunks.append(seed.format(index=index))
        index += 1
    return "\n".join(chunks)


def choose_gemini_model(client: httpx.Client, api_key: str, base_url: str) -> str:
    response = client.get(
        f"{base_url.rstrip('/')}/models",
        headers={"x-goog-api-key": api_key},
    )
    response.raise_for_status()
    models = response.json().get("models", [])
    candidates: list[str] = []
    for model in models:
        name = model.get("name", "")
        methods = model.get("supportedGenerationMethods") or model.get("supportedActions") or []
        if "generateContent" not in methods:
            continue
        short = name.removeprefix("models/")
        if "flash" in short.lower():
            candidates.append(short)
    if not candidates:
        raise RuntimeError("no Gemini Flash model supporting generateContent is available")

    def rank(name: str) -> tuple[int, str]:
        lowered = name.lower()
        preview_penalty = 1 if ("preview" in lowered or "exp" in lowered) else 0
        return (preview_penalty, lowered)

    return sorted(candidates, key=rank)[0]


def build_adapter(provider: str):
    if provider == "openai":
        return OpenAIResponsesAdapter(
            api_key=os.environ["OPENAI_API_KEY"],
            model=os.getenv("OPENAI_LIVE_MODEL", "gpt-5.6-luna"),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
        )
    if provider == "gemini":
        api_key = os.environ["GEMINI_API_KEY"]
        base_url = os.getenv(
            "GEMINI_BASE_URL",
            "https://generativelanguage.googleapis.com/v1beta",
        ).rstrip("/")
        client = httpx.Client(timeout=120.0)
        model = choose_gemini_model(client, api_key, base_url)
        return GeminiGenerateContentAdapter(
            api_key=api_key,
            model=model,
            base_url=base_url,
            client=client,
        )
    raise ValueError(f"unsupported provider: {provider}")


def run(provider: str, sizes: tuple[int, ...]) -> dict:
    memory = EnterpriseMemoryService(OrganizationIdentity(f"live-scale-{provider}"))
    scope = MemoryScope(f"live-scale-{provider}")
    memory.remember(
        scope,
        f"live-scale-{provider}-memory",
        FACT_TEXT,
        ("key", FACT_KEY),
        provenance="live-context-scale-v1",
    )
    chat = ProductChatService(memory, build_adapter(provider))

    cases: list[dict] = []
    for target_tokens in sizes:
        baseline_context = make_baseline_context(target_tokens)

        baseline = chat.run(
            scope=scope,
            message=QUESTION,
            mode="baseline",
            baseline_context=(baseline_context,),
        )
        memoria = chat.run(
            scope=scope,
            message=QUESTION,
            mode="memoria",
            memory_keys=(FACT_KEY,),
        )

        reduction = token_reduction(
            baseline_tokens=baseline.metrics.input_tokens,
            memoria_tokens=memoria.metrics.input_tokens,
        )
        cases.append(
            {
                "target_history_tokens": target_tokens,
                "baseline": {
                    **baseline.metrics.as_dict(),
                    "response_nonempty": bool(baseline.text.strip()),
                    "response_mentions_expected_fact": "cobalt" in baseline.text.lower(),
                },
                "memoria": {
                    **memoria.metrics.as_dict(),
                    "response_nonempty": bool(memoria.text.strip()),
                    "response_mentions_expected_fact": "cobalt" in memoria.text.lower(),
                },
                "token_reduction": reduction,
                "token_reduction_percent": None if reduction is None else reduction * 100.0,
            }
        )

    report = {
        "benchmark": "memoria.ia-live-context-scale-v1",
        "experimental_isolation": True,
        "provider": provider,
        "sizes": list(sizes),
        "cases": cases,
        "claims": {
            "provider_usage_tokens": True,
            "semantic_discovery_benchmarked": False,
            "memory_keys_supplied_explicitly": True,
        },
        "limitations": [
            "This benchmark measures context selection with explicit memory keys, not semantic discovery.",
            "The baseline embeds the expected fact near the beginning of a long irrelevant history.",
            "Provider latency and model behavior can vary across executions.",
            "No pricing claim is made unless the adapter reports a configured estimated cost.",
        ],
    }
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=("openai", "gemini"), required=True)
    parser.add_argument("--sizes", nargs="+", type=int, default=list(DEFAULT_SIZES))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    report = run(args.provider, tuple(args.sizes))
    rendered = json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")

    for case in report["cases"]:
        assert case["baseline"]["response_nonempty"] is True
        assert case["baseline"]["response_mentions_expected_fact"] is True
        assert case["memoria"]["response_nonempty"] is True
        assert case["memoria"]["response_mentions_expected_fact"] is True
        assert case["memoria"]["memory_hits"] == 1
        assert case["memoria"]["memory_misses"] == 0
        assert case["token_reduction"] is not None
        assert case["token_reduction"] > 0


if __name__ == "__main__":
    main()
