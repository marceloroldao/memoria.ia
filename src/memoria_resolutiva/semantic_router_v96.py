from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

from .textual import TextContextMemory


@dataclass(frozen=True, slots=True)
class SemanticResolution:
    query: str
    concept_id: str | None
    score: float
    margin: float
    source: str


@dataclass(frozen=True, slots=True)
class DeflectionMetrics:
    total_queries: int
    memory_resolved: int
    fallback_calls: int

    @property
    def deflection_rate(self) -> float:
        if self.total_queries == 0:
            return 0.0
        return self.memory_resolved / self.total_queries


class SemanticRouterV96:
    """Conservative non-neural semantic routing experiment.

    A concept is represented by one or more textual anchors. A query is routed
    to a concept only when contextual evidence is strong enough and sufficiently
    separated from the runner-up. Otherwise the router returns unresolved and a
    caller may invoke a neural or other external fallback.

    This module does not claim general language understanding.
    """

    def __init__(
        self,
        *,
        radius: int = 3,
        threshold: float = 0.60,
        min_margin: float = 0.08,
    ) -> None:
        self.memory = TextContextMemory(radius=radius)
        self.threshold = threshold
        self.min_margin = min_margin
        self._concepts: dict[str, set[str]] = {}
        self._total_queries = 0
        self._memory_resolved = 0
        self._fallback_calls = 0

    def observe(self, sentences: Iterable[str]) -> None:
        self.memory.observe_many(sentences)

    def register_concept(self, concept_id: str, anchors: Iterable[str]) -> None:
        normalized = {a.strip().lower() for a in anchors if a.strip()}
        if not normalized:
            raise ValueError("concept must have at least one anchor")
        self._concepts.setdefault(concept_id, set()).update(normalized)

    def _score(self, query: str, anchor: str) -> float:
        return max(
            self.memory.similarity(query, anchor),
            self.memory.unordered_similarity(query, anchor),
        )

    def resolve_token(self, query: str) -> SemanticResolution:
        q = query.strip().lower()
        if not q:
            raise ValueError("query must not be empty")
        ranked: list[tuple[str, float]] = []
        for concept_id, anchors in self._concepts.items():
            best = max((self._score(q, anchor) for anchor in anchors), default=0.0)
            ranked.append((concept_id, best))
        ranked.sort(key=lambda item: (-item[1], item[0]))
        if not ranked:
            return SemanticResolution(q, None, 0.0, 0.0, "unresolved")

        best_id, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best_score - second_score
        if best_score >= self.threshold and margin >= self.min_margin:
            return SemanticResolution(q, best_id, best_score, margin, "memory")
        return SemanticResolution(q, None, best_score, margin, "unresolved")

    def resolve_or_fallback(
        self,
        query: str,
        fallback: Callable[[str], str | None],
    ) -> SemanticResolution:
        self._total_queries += 1
        direct = self.resolve_token(query)
        if direct.concept_id is not None:
            self._memory_resolved += 1
            return direct

        self._fallback_calls += 1
        concept_id = fallback(query)
        return SemanticResolution(
            query.strip().lower(),
            concept_id,
            direct.score,
            direct.margin,
            "fallback",
        )

    def metrics(self) -> DeflectionMetrics:
        return DeflectionMetrics(
            total_queries=self._total_queries,
            memory_resolved=self._memory_resolved,
            fallback_calls=self._fallback_calls,
        )
