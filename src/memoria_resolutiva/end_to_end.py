from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .baselines import WindowCooccurrenceBaseline
from .textual import TextContextMemory
from .tfidf_context import TfidfContextBaseline


@dataclass(frozen=True, slots=True)
class EndToEndStep:
    step: int
    observations: int
    resolutive_update_seconds: float
    cooccurrence_update_seconds: float
    tfidf_rebuild_seconds: float
    resolutive_immediate_top1: float
    resolutive_retention_top1: float
    cooccurrence_retention_top1: float
    tfidf_retention_top1: float
    resolutive_nodes: int
    resolutive_features: int
    cooccurrence_nodes: int
    cooccurrence_features: int


class EndToEndOnlineBenchmark:
    """Compare online incorporation, immediate use, retention and model growth.

    Resolutive Memory and the cooccurrence baseline are updated incrementally with
    only the incoming batch. The TF-IDF-like baseline is deliberately rebuilt from
    the complete accumulated corpus after every batch, representing a retraining
    workflow. Timing values are environment-specific; tests should validate
    invariants rather than absolute speed ratios.
    """

    def __init__(self, radius: int = 3):
        self.radius = radius
        self.resolutive = TextContextMemory(radius=radius)
        self.cooccurrence = WindowCooccurrenceBaseline(radius=radius)
        self.tfidf = TfidfContextBaseline(radius=radius)
        self.history: list[str] = []
        self.pairs: list[tuple[str, str]] = []
        self.observations = 0

    @staticmethod
    def _candidate_tokens(pairs: list[tuple[str, str]]) -> list[str]:
        return list(dict.fromkeys(token for pair in pairs for token in pair))

    def _resolutive_accuracy(self, pairs: list[tuple[str, str]]) -> float:
        if not pairs:
            return 1.0
        candidates = self._candidate_tokens(pairs)
        checks: list[bool] = []
        for a, b in pairs:
            for query, target in ((a, b), (b, a)):
                ranked = [
                    (candidate, self.resolutive.associator.similarity(query, candidate))
                    for candidate in candidates
                    if candidate != query
                ]
                ranked.sort(key=lambda item: item[1], reverse=True)
                checks.append(bool(ranked and ranked[0][0] == target))
        return sum(checks) / len(checks)

    @staticmethod
    def _baseline_accuracy(model, pairs: list[tuple[str, str]]) -> float:
        if not pairs:
            return 1.0
        candidates = EndToEndOnlineBenchmark._candidate_tokens(pairs)
        checks: list[bool] = []
        for a, b in pairs:
            for query, target in ((a, b), (b, a)):
                ranked = model.nearest(query, candidates, top_k=1)
                checks.append(bool(ranked and ranked[0][0] == target))
        return sum(checks) / len(checks)

    def observe_batch(self, sentences: list[str], expected_pair: tuple[str, str]) -> EndToEndStep:
        old_pairs = list(self.pairs)

        start = perf_counter()
        self.resolutive.observe_many(sentences)
        resolutive_update = perf_counter() - start

        start = perf_counter()
        self.cooccurrence.observe_many(sentences)
        cooccurrence_update = perf_counter() - start

        self.history.extend(sentences)
        start = perf_counter()
        rebuilt = TfidfContextBaseline(radius=self.radius)
        rebuilt.observe_many(self.history)
        self.tfidf = rebuilt
        tfidf_rebuild = perf_counter() - start

        self.observations += len(sentences)
        immediate = self._resolutive_accuracy([expected_pair])
        resolutive_retention = self._resolutive_accuracy(old_pairs)
        cooccurrence_retention = self._baseline_accuracy(self.cooccurrence, old_pairs)
        tfidf_retention = self._baseline_accuracy(self.tfidf, old_pairs)
        self.pairs.append(expected_pair)

        footprint = self.resolutive.associator.footprint()
        cooc_features = sum(len(profile) for profile in self.cooccurrence.profiles.values())

        return EndToEndStep(
            step=len(self.pairs),
            observations=self.observations,
            resolutive_update_seconds=resolutive_update,
            cooccurrence_update_seconds=cooccurrence_update,
            tfidf_rebuild_seconds=tfidf_rebuild,
            resolutive_immediate_top1=immediate,
            resolutive_retention_top1=resolutive_retention,
            cooccurrence_retention_top1=cooccurrence_retention,
            tfidf_retention_top1=tfidf_retention,
            resolutive_nodes=footprint["nodes"],
            resolutive_features=footprint["features"],
            cooccurrence_nodes=len(self.cooccurrence.profiles),
            cooccurrence_features=cooc_features,
        )
