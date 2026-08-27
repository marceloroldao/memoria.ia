from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import sqrt
from typing import Iterable

from .textual import tokenize


@dataclass(frozen=True, slots=True)
class StructuralEvidence:
    concept_id: str
    matched_weight: float
    query_weight: float
    profile_weight: float
    score: float


@dataclass(frozen=True, slots=True)
class StructuralResolution:
    text: str
    concept_id: str | None
    score: float
    margin: float
    source: str
    evidence: tuple[StructuralEvidence, ...]


class StructuralSemanticRouterV96:
    """Experimental non-neural phrase router based on ordered relation signatures.

    A registered example becomes a sparse set of directional pair features
    ``(left_token, signed_offset, right_token)``.  Unlike bag-of-words routing,
    reversing subject/object order changes the signature even when the token set
    is identical.
    """

    def __init__(self, *, relation_window: int = 3, threshold: float = 0.55, min_margin: float = 0.08):
        if relation_window < 1:
            raise ValueError("relation_window must be >= 1")
        self.relation_window = relation_window
        self.threshold = threshold
        self.min_margin = min_margin
        self._profiles: dict[str, Counter[tuple[str, int, str]]] = defaultdict(Counter)

    def _features(self, text: str) -> Counter[tuple[str, int, str]]:
        tokens = tokenize(text)
        features: Counter[tuple[str, int, str]] = Counter()
        for i, left in enumerate(tokens):
            hi = min(len(tokens), i + self.relation_window + 1)
            for j in range(i + 1, hi):
                right = tokens[j]
                offset = j - i
                features[(left, offset, right)] += 1
                features[(right, -offset, left)] += 1
        return features

    def register_pattern(self, concept_id: str, text: str, *, repeat: int = 1) -> None:
        if not concept_id.strip():
            raise ValueError("concept_id must not be empty")
        if repeat < 1:
            raise ValueError("repeat must be >= 1")
        features = self._features(text)
        if not features:
            raise ValueError("pattern must contain at least two tokens")
        for feature, count in features.items():
            self._profiles[concept_id][feature] += count * repeat

    def register_many(self, concept_id: str, patterns: Iterable[str]) -> None:
        for pattern in patterns:
            self.register_pattern(concept_id, pattern)

    @staticmethod
    def _cosine(query: Counter, profile: Counter) -> tuple[float, float, float, float]:
        if not query or not profile:
            return 0.0, 0.0, 0.0, 0.0
        common = set(query) & set(profile)
        dot = sum(float(query[f]) * float(profile[f]) for f in common)
        qnorm = sqrt(sum(float(v) * float(v) for v in query.values()))
        pnorm = sqrt(sum(float(v) * float(v) for v in profile.values()))
        score = dot / (qnorm * pnorm) if qnorm and pnorm else 0.0
        return score, dot, qnorm, pnorm

    def resolve_text(self, text: str) -> StructuralResolution:
        normalized = text.strip().lower()
        query = self._features(normalized)
        if not query or not self._profiles:
            return StructuralResolution(normalized, None, 0.0, 0.0, "unresolved", ())

        evidence = []
        for concept_id, profile in self._profiles.items():
            score, dot, qnorm, pnorm = self._cosine(query, profile)
            evidence.append(StructuralEvidence(concept_id, dot, qnorm, pnorm, score))
        evidence.sort(key=lambda item: (-item.score, item.concept_id))

        best = evidence[0]
        second_score = evidence[1].score if len(evidence) > 1 else 0.0
        margin = best.score - second_score
        if best.score >= self.threshold and margin >= self.min_margin:
            return StructuralResolution(normalized, best.concept_id, best.score, margin, "structural", tuple(evidence[:5]))
        return StructuralResolution(normalized, None, best.score, margin, "unresolved", tuple(evidence[:5]))
