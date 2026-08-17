from __future__ import annotations

from collections import Counter, defaultdict
from math import log, sqrt

from .textual import tokenize


class TfidfContextBaseline:
    """Sparse unordered TF-IDF-like context-vector baseline.

    Each token accumulates neighboring-token counts inside a fixed symmetric
    window. Relative direction and offset are intentionally discarded, making
    this a stronger baseline than raw cooccurrence while remaining non-neural.
    """

    def __init__(self, radius: int = 3):
        if radius < 1:
            raise ValueError("radius must be >= 1")
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

    def _document_frequency(self) -> Counter[str]:
        df: Counter[str] = Counter()
        for profile in self.profiles.values():
            for feature in profile:
                df[feature] += 1
        return df

    def similarity(self, a: str, b: str) -> float:
        a = a.lower()
        b = b.lower()
        pa = self.profiles.get(a)
        pb = self.profiles.get(b)
        if not pa or not pb:
            return 0.0

        df = self._document_frequency()
        total = max(1, len(self.profiles))

        def weight(feature: str) -> float:
            return log((total + 1) / (df[feature] + 1)) + 1.0

        shared = set(pa) & set(pb)
        dot = sum(pa[f] * pb[f] * weight(f) ** 2 for f in shared)
        norm_a = sqrt(sum((v * weight(f)) ** 2 for f, v in pa.items()))
        norm_b = sqrt(sum((v * weight(f)) ** 2 for f, v in pb.items()))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0

    def nearest(self, token: str, candidates, top_k: int = 5):
        token = token.lower()
        ranked = [
            (candidate, self.similarity(token, candidate))
            for candidate in candidates
            if candidate != token
        ]
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked[:top_k]
