from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import log, sqrt
from typing import Iterable

from .textual import tokenize


_STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos",
    "e", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem",
    "que", "foi", "esta", "este", "esse", "essa", "ao", "aos", "se",
    "mas", "porque", "como", "ainda", "depois", "antes", "muito", "mais",
    "menos", "ja", "nao",
}


@dataclass(frozen=True, slots=True)
class SentenceResolution:
    concept_id: str | None
    score: float
    margin: float
    source: str


class SentenceSemanticRouterV96:
    """Experimental sentence-level sparse semantic router.

    Unlike the token router, this experiment scores the full content-word profile
    of a query sentence against concept profiles learned from example sentences.
    It uses sparse counters and inverse concept frequency only; no embedding or
    neural network is involved.
    """

    def __init__(self, *, threshold: float = 0.14, min_margin: float = 0.02) -> None:
        self.threshold = threshold
        self.min_margin = min_margin
        self._profiles: dict[str, Counter[str]] = {}
        self._df: Counter[str] = Counter()
        self._dirty = True

    @staticmethod
    def _content_profile(text: str) -> Counter[str]:
        return Counter(token for token in tokenize(text) if token not in _STOPWORDS)

    def observe_concept(self, concept_id: str, examples: Iterable[str]) -> None:
        if not concept_id:
            raise ValueError("concept_id must not be empty")
        profile = self._profiles.setdefault(concept_id, Counter())
        count = 0
        for sentence in examples:
            profile.update(self._content_profile(sentence))
            count += 1
        if count == 0:
            raise ValueError("concept must have at least one example")
        self._dirty = True

    def _rebuild_df(self) -> None:
        df: Counter[str] = Counter()
        for profile in self._profiles.values():
            for token in profile:
                df[token] += 1
        self._df = df
        self._dirty = False

    def _weight(self, token: str) -> float:
        n = max(1, len(self._profiles))
        return log((n + 1) / (self._df.get(token, 0) + 1)) + 1.0

    def _score(self, query: Counter[str], concept: Counter[str]) -> float:
        if not query or not concept:
            return 0.0
        shared = set(query) & set(concept)
        dot = sum(query[t] * concept[t] * self._weight(t) ** 2 for t in shared)
        nq = sqrt(sum((v * self._weight(t)) ** 2 for t, v in query.items()))
        nc = sqrt(sum((v * self._weight(t)) ** 2 for t, v in concept.items()))
        if nq == 0.0 or nc == 0.0:
            return 0.0
        return dot / (nq * nc)

    def resolve(self, sentence: str) -> SentenceResolution:
        if self._dirty:
            self._rebuild_df()
        query = self._content_profile(sentence)
        if not query or not self._profiles:
            return SentenceResolution(None, 0.0, 0.0, "unresolved")

        ranked = sorted(
            ((concept_id, self._score(query, profile)) for concept_id, profile in self._profiles.items()),
            key=lambda item: (-item[1], item[0]),
        )
        best_id, best_score = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best_score - second
        if best_score >= self.threshold and margin >= self.min_margin:
            return SentenceResolution(best_id, best_score, margin, "memory")
        return SentenceResolution(None, best_score, margin, "unresolved")
