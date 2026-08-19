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


@dataclass(frozen=True, slots=True)
class NoveltyDiagnostics:
    predicted_concept_id: str | None
    shared_terms: int
    query_terms: int
    shared_term_fraction: float
    weighted_query_coverage: float
    score: float
    margin: float


class SentenceSemanticRouterV96:
    """Experimental sentence-level sparse semantic router.

    Unlike the token router, this experiment scores the full content-word profile
    of a query sentence against concept profiles learned from example sentences.
    It uses sparse counters and inverse concept frequency only; no embedding or
    neural network is involved.

    v0.96 exposes novelty diagnostics separately from the acceptance rule so that
    open-set rejection can be calibrated experimentally without silently changing
    the semantic classifier.
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

    def _rank(self, sentence: str):
        if self._dirty:
            self._rebuild_df()
        query = self._content_profile(sentence)
        if not query or not self._profiles:
            return query, []
        ranked = sorted(
            ((concept_id, self._score(query, profile)) for concept_id, profile in self._profiles.items()),
            key=lambda item: (-item[1], item[0]),
        )
        return query, ranked

    def resolve(self, sentence: str) -> SentenceResolution:
        query, ranked = self._rank(sentence)
        if not query or not ranked:
            return SentenceResolution(None, 0.0, 0.0, "unresolved")

        best_id, best_score = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best_score - second
        if best_score >= self.threshold and margin >= self.min_margin:
            return SentenceResolution(best_id, best_score, margin, "memory")
        return SentenceResolution(None, best_score, margin, "unresolved")

    def novelty_diagnostics(self, sentence: str) -> NoveltyDiagnostics:
        query, ranked = self._rank(sentence)
        if not query or not ranked:
            return NoveltyDiagnostics(None, 0, len(query), 0.0, 0.0, 0.0, 0.0)

        best_id, best_score = ranked[0]
        second = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best_score - second
        concept = self._profiles[best_id]
        shared = set(query) & set(concept)
        query_terms = len(query)
        shared_terms = len(shared)
        shared_fraction = shared_terms / query_terms if query_terms else 0.0

        total_query_weight = sum(query[t] * self._weight(t) for t in query)
        shared_query_weight = sum(query[t] * self._weight(t) for t in shared)
        weighted_coverage = (
            shared_query_weight / total_query_weight if total_query_weight > 0 else 0.0
        )
        predicted = (
            best_id if best_score >= self.threshold and margin >= self.min_margin else None
        )
        return NoveltyDiagnostics(
            predicted_concept_id=predicted,
            shared_terms=shared_terms,
            query_terms=query_terms,
            shared_term_fraction=shared_fraction,
            weighted_query_coverage=weighted_coverage,
            score=best_score,
            margin=margin,
        )
