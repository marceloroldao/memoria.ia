from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .textual import TextContextMemory


@dataclass(frozen=True, slots=True)
class StreamingCheckpoint:
    batch: int
    sentences_seen: int
    update_seconds: float
    immediate_top1: float
    retention_top1: float
    nodes: int
    features: int
    feature_df_entries: int


class StreamingLearningEvaluator:
    """Continual-learning probe for heterogeneous sequential batches.

    New batches are appended once to the existing memory. Previous observations
    are never replayed. At each checkpoint the evaluator measures immediate
    acquisition, retention of previously introduced relations, update latency and
    sparse structural growth.
    """

    def __init__(self, radius: int = 3):
        self.memory = TextContextMemory(radius=radius)
        self.learned_pairs: list[tuple[str, str]] = []
        self.sentences_seen = 0
        self.batch = 0

    def _top1(self, query: str, target: str) -> bool:
        ranked = self.memory.nearest(query, top_k=1)
        return bool(ranked and ranked[0][0] == target)

    def _pair_accuracy(self, pairs: list[tuple[str, str]]) -> float:
        if not pairs:
            return 1.0
        hits = 0
        total = 0
        for a, b in pairs:
            hits += int(self._top1(a, b))
            hits += int(self._top1(b, a))
            total += 2
        return hits / total

    def observe_batch(
        self,
        sentences: list[str],
        expected_pair: tuple[str, str] | None = None,
        measure_retention: bool = True,
    ) -> StreamingCheckpoint:
        before = list(self.learned_pairs)
        start = perf_counter()
        self.memory.observe_many(sentences)
        elapsed = perf_counter() - start
        self.sentences_seen += len(sentences)
        self.batch += 1

        immediate = 1.0
        if expected_pair is not None:
            immediate = self._pair_accuracy([expected_pair])
            if expected_pair not in self.learned_pairs:
                self.learned_pairs.append(expected_pair)

        retention = self._pair_accuracy(before) if measure_retention else float("nan")
        footprint = self.memory.associator.footprint()
        return StreamingCheckpoint(
            batch=self.batch,
            sentences_seen=self.sentences_seen,
            update_seconds=elapsed,
            immediate_top1=immediate,
            retention_top1=retention,
            nodes=footprint["nodes"],
            features=footprint["features"],
            feature_df_entries=footprint["feature_df_entries"],
        )
