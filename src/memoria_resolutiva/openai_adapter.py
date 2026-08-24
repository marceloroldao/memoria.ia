from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import httpx

from .llm_adapter import LLMAdapterError, LLMResponse, LLMUsage


@dataclass(frozen=True, slots=True)
class OpenAIPricing:
    input_usd_per_million: float | None = None
    output_usd_per_million: float | None = None

    def estimate(self, input_tokens: int | None, output_tokens: int | None) -> float | None:
        if (
            input_tokens is None
            or output_tokens is None
            or self.input_usd_per_million is None
            or self.output_usd_per_million is None
        ):
            return None
        return (
            input_tokens * self.input_usd_per_million
            + output_tokens * self.output_usd_per_million
        ) / 1_000_000.0


class OpenAIResponsesAdapter:
    """Optional OpenAI adapter using the Responses API.

    No private Memoria.ia hash is sent as a substitute for context. Selected
    memory is materialized into text before the external request.
    """

    provider_name = "openai"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 60.0,
        pricing: OpenAIPricing | None = None,
        client: httpx.Client | None = None,
    ):
        if not api_key:
            raise ValueError("OpenAI api_key must be configured")
        if not model:
            raise ValueError("OpenAI model must be configured")
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._pricing = pricing or OpenAIPricing()
        self._client = client or httpx.Client(timeout=timeout_seconds)

    @property
    def model_name(self) -> str:
        return self._model

    @staticmethod
    def _input_text(message: str, context: Sequence[str]) -> str:
        if not context:
            return message
        rendered = "\n\n".join(f"[Memory {i}]\n{item}" for i, item in enumerate(context, start=1))
        return (
            "Use the following selected memory only when relevant. "
            "Do not assume it is complete or always correct.\n\n"
            f"{rendered}\n\n[User]\n{message}"
        )

    @staticmethod
    def _output_text(data: dict) -> str:
        chunks: list[str] = []
        for item in data.get("output", []):
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content", []):
                if isinstance(content, dict) and content.get("type") == "output_text":
                    text = content.get("text")
                    if isinstance(text, str):
                        chunks.append(text)
        if not chunks:
            raise LLMAdapterError("OpenAI response did not contain output_text")
        return "".join(chunks)

    def generate(self, *, message: str, context: Sequence[str]) -> LLMResponse:
        try:
            response = self._client.post(
                f"{self._base_url}/responses",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "input": self._input_text(message, context),
                },
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMAdapterError("OpenAI request failed") from exc

        usage = data.get("usage") or {}
        input_tokens = usage.get("input_tokens")
        output_tokens = usage.get("output_tokens")
        if not isinstance(input_tokens, int):
            input_tokens = None
        if not isinstance(output_tokens, int):
            output_tokens = None

        return LLMResponse(
            text=self._output_text(data),
            provider=self.provider_name,
            model=self._model,
            usage=LLMUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_usd=self._pricing.estimate(input_tokens, output_tokens),
            ),
        )
