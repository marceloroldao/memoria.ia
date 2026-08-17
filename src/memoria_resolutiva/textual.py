from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from math import log2, sqrt

from .contextual import ContextAssociator

_TOKEN_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Small deterministic tokenizer for v0.7 natural-language experiments."""
    return [token.lower() for token in _TOKEN_RE.findall(text)]


@dataclass(frozen=True, slots=True)
class AmbiguityProbe:
    token: str
    alternatives: tuple[tuple[str, float], ...]
    normalized_entropy: float
    margin: float


class TextContextMemory:
    """Natural-language adapter over sparse resolutive contextual association."""

    def __init__(self, radius: int = 3):
        self.associator = ContextAssociator(radius=radius)

    def observe_sentence(self, sentence: str) -> None:
        tokens = tokenize(sentence)
        if tokens:
            self.associator.observe(tokens)

    def observe_many(self, sentences) -> None:
        for sentence in sentences:
            self.observe_sentence(sentence)

    def similarity(self, a: str, b: str) -> float:
        """Position-sensitive contextual similarity used by trajectory experiments."""
        return self.associator.similarity(a.lower(), b.lower())

    def unordered_similarity(self, a: str, b: str) -> float:
        """Compare contextual neighborhoods while ignoring relative offsets.

        This is intended for lexical/ontology grouping, where small grammatical
        shifts (article choice, inflection, or one-position displacement) should
        not erase otherwise strong contextual evidence. The original
        position-sensitive similarity remains unchanged for trajectory work.
        """
        pa = self.associator.profiles.get(a.lower())
        pb = self.associator.profiles.get(b.lower())
        if not pa or not pb:
            return 0.0

        ca: Counter[str] = Counter()
        cb: Counter[str] = Counter()
        for (_offset, token), count in pa.items():
            ca[token] += count
        for (_offset, token), count in pb.items():
            cb[token] += count

        shared = set(ca) & set(cb)
        dot = sum(ca[token] * cb[token] for token in shared)
        norm_a = sqrt(sum(value * value for value in ca.values()))
        norm_b = sqrt(sum(value * value for value in cb.values()))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return dot / (norm_a * norm_b)

    def nearest(self, token: str, top_k: int = 5) -> list[tuple[str, float]]:
        return self.associator.nearest(token.lower(), top_k=top_k)

    def ambiguity_probe(self, token: str, top_k: int = 5) -> AmbiguityProbe:
        ranked = self.nearest(token, top_k=top_k)
        positive = [(node, max(0.0, score)) for node, score in ranked if score > 0]
        total = sum(score for _, score in positive)
        if total <= 0 or len(positive) <= 1:
            entropy = 0.0
        else:
            probs = [score / total for _, score in positive]
            raw = -sum(p * log2(p) for p in probs if p > 0)
            entropy = raw / log2(len(probs))
        margin = 0.0
        if ranked:
            margin = ranked[0][1] - (ranked[1][1] if len(ranked) > 1 else 0.0)
        return AmbiguityProbe(token.lower(), tuple(ranked), entropy, margin)
