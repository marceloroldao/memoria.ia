from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import sqrt
from typing import Callable, Iterable

from .textual import tokenize


@dataclass(frozen=True, slots=True)
class SenseResolution:
    surface: str
    concept_id: str | None
    score: float
    margin: float
    source: str


class PolysemyRouterV96:
    """Context-sensitive non-neural sense routing.

    Each concept is learned from example sentences. Resolution compares the
    query sentence context against concept-specific sparse context profiles.
    The ambiguous surface token itself is removed from the profile so the
    decision depends on surrounding evidence rather than the word identity.

    The router deliberately abstains when score or runner-up margin is too low.
    """

    def __init__(self, *, threshold: float = 0.25, min_margin: float = 0.08) -> None:
        self.threshold = threshold
        self.min_margin = min_margin
        self._profiles: dict[tuple[str, str], Counter[str]] = {}
        self._total = 0
        self._resolved = 0
        self._fallback = 0

    @staticmethod
    def _context(sentence: str, surface: str) -> Counter[str]:
        s = surface.strip().lower()
        tokens = tokenize(sentence)
        return Counter(t for t in tokens if t != s)

    @staticmethod
    def _cosine(a: Counter[str], b: Counter[str]) -> float:
        if not a or not b:
            return 0.0
        shared = set(a) & set(b)
        dot = sum(a[t] * b[t] for t in shared)
        na = sqrt(sum(v * v for v in a.values()))
        nb = sqrt(sum(v * v for v in b.values()))
        if na == 0.0 or nb == 0.0:
            return 0.0
        return dot / (na * nb)

    def observe_sense(self, surface: str, concept_id: str, examples: Iterable[str]) -> None:
        key = (surface.strip().lower(), concept_id)
        if not key[0] or not concept_id:
            raise ValueError("surface and concept_id must not be empty")
        profile = self._profiles.setdefault(key, Counter())
        count = 0
        for sentence in examples:
            profile.update(self._context(sentence, key[0]))
            count += 1
        if count == 0:
            raise ValueError("sense must have at least one example")

    def resolve(self, surface: str, sentence: str) -> SenseResolution:
        s = surface.strip().lower()
        query = self._context(sentence, s)
        ranked: list[tuple[str, float]] = []
        for (known_surface, concept_id), profile in self._profiles.items():
            if known_surface == s:
                ranked.append((concept_id, self._cosine(query, profile)))
        ranked.sort(key=lambda x: (-x[1], x[0]))
        if not ranked:
            return SenseResolution(s, None, 0.0, 0.0, "unresolved")
        best_id, best_score = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best_score - second
        if best_score >= self.threshold and margin >= self.min_margin:
            return SenseResolution(s, best_id, best_score, margin, "memory")
        return SenseResolution(s, None, best_score, margin, "unresolved")

    def resolve_or_fallback(
        self,
        surface: str,
        sentence: str,
        fallback: Callable[[str, str], str | None],
    ) -> SenseResolution:
        self._total += 1
        direct = self.resolve(surface, sentence)
        if direct.concept_id is not None:
            self._resolved += 1
            return direct
        self._fallback += 1
        concept_id = fallback(surface, sentence)
        return SenseResolution(direct.surface, concept_id, direct.score, direct.margin, "fallback")

    def metrics(self) -> dict[str, float | int]:
        return {
            "total_queries": self._total,
            "memory_resolved": self._resolved,
            "fallback_calls": self._fallback,
            "deflection_rate": self._resolved / self._total if self._total else 0.0,
        }
