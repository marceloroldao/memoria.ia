from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence


@dataclass(frozen=True, slots=True)
class LLMUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    estimated_cost_usd: float | None = None


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str
    provider: str
    model: str
    usage: LLMUsage = LLMUsage()


class LLMAdapter(Protocol):
    """Provider-neutral boundary used by Memoria.ia Enterprise.

    Context passed here must already be materialized text. A Memoria.ia private
    state/hash is not assumed to carry meaning for an external provider.
    """

    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def generate(self, *, message: str, context: Sequence[str]) -> LLMResponse: ...


def estimate_tokens(text: str) -> int:
    """Deterministic fallback estimate, explicitly not a provider tokenizer."""
    if not text:
        return 0
    # Character-based approximation keeps benchmarks reproducible without
    # coupling the product core to a provider tokenizer.
    return max(1, (len(text) + 3) // 4)


class MockLLMAdapter:
    """Deterministic test adapter. It is not a language model."""

    provider_name = "mock"
    model_name = "deterministic-echo-v1"

    def generate(self, *, message: str, context: Sequence[str]) -> LLMResponse:
        materialized = "\n".join(context)
        prompt = f"CONTEXT:\n{materialized}\n\nMESSAGE:\n{message}" if materialized else message
        response = f"mock:{message}"
        return LLMResponse(
            text=response,
            provider=self.provider_name,
            model=self.model_name,
            usage=LLMUsage(
                input_tokens=estimate_tokens(prompt),
                output_tokens=estimate_tokens(response),
                estimated_cost_usd=0.0,
            ),
        )
