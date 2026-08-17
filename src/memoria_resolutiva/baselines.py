from __future__ import annotations

from collections import Counter, defaultdict
from math import sqrt

from .textual import tokenize


class WindowCooccurrenceBaseline:
    """Unordered local cooccurrence baseline for v0.8 comparisons."""

    def __init__(self, radius: int = 3):
        self.radius = radius
        self.profiles: dict[str, Counter[str]] = defaultdict(Counter)

    def observe_sentence(self, sentence: str) -> None:
        tokens = tokenize(sentence)
        for i, token in enumerate(tokens):
            lo = max(0, i - self.radius)
            hi = min(len(tokens), i + self.radius + 1)
            for j in range(lo, hi):
                if j != i:
                    self.profiles[token][tokens[j]] += 1

    def observe_many(self, sentences) -> None:
        for sentence in sentences:
            self.observe_sentence(sentence)

    def similarity(self, a: str, b: str) -> float:
        pa = self.profiles.get(a.lower())
        pb = self.profiles.get(b.lower())
        if not pa or not pb:
            return 0.0
        shared = set(pa) & set(pb)
        dot = sum(pa[f] * pb[f] for f in shared)
        norm_a = sqrt(sum(v * v for v in pa.values()))
        norm_b = sqrt(sum(v * v for v in pb.values()))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def nearest(self, token: str, candidates, top_k: int = 5):
        ranked = [
            (candidate, self.similarity(token, candidate))
            for candidate in candidates
            if candidate.lower() != token.lower()
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:top_k]
