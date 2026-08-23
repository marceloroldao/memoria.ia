from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import httpx

from .llm_adapter import LLMAdapterError, LLMResponse, LLMUsage


@dataclass(frozen=True, slots=True)
class GeminiPricing:
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


class GeminiGenerateContentAdapter:
    """Optional Gemini adapter using Google AI generateContent.

    Selected Memoria.ia context is materialized into text before the request.
    Private state identifiers/hashes are never treated as provider-readable context.
    """

    provider_name = "gemini"

    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 60.0,
        pricing: GeminiPricing | None = None,
        client: httpx.Client | None = None,
    ):
        if not api_key:
            raise ValueError("Gemini api_key must be configured")
        if not model:
            raise ValueError("Gemini model must be configured")
        self._api_key = api_key
        self._model = model.removeprefix("models/")
        self._base_url = base_url.rstrip("/")
        self._pricing = pricing or GeminiPricing()
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
        for candidate in data.get("candidates", []):
            if not isinstance(candidate, dict):
                continue
            content = candidate.get("content") or {}
            if not isinstance(content, dict):
                continue
            for part in content.get("parts", []):
                if not isinstance(part, dict):
                    continue
                text = part.get("text")
                if isinstance(text, str):
                    chunks.append(text)
            if chunks:
                break
        if not chunks:
            raise LLMAdapterError("Gemini response did not contain text output")
        return "".join(chunks)

    def generate(self, *, message: str, context: Sequence[str]) -> LLMResponse:
        try:
            response = self._client.post(
                f"{self._base_url}/models/{self._model}:generateContent",
                headers={
                    "x-goog-api-key": self._api_key,
                    "Content-Type": "application/json",
                },
                json={
                    "contents": [
                        {
                            "role": "user",
                            "parts": [{"text": self._input_text(message, context)}],
                        }
                    ]
                },
            )
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMAdapterError("Gemini request failed") from exc

        usage = data.get("usageMetadata") or {}
        input_tokens = usage.get("promptTokenCount")
        output_tokens = usage.get("candidatesTokenCount")
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
