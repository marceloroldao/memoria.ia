from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter

from .textual import TextContextMemory


@dataclass(frozen=True, slots=True)
class OnlineStep:
    step: int
    observations: int
    update_seconds: float
    immediate_top1: float
    retention_top1: float


class OnlineLearningEvaluator:
    """Evaluate incremental learning without replaying prior observations.

    Each batch is appended to the existing TextContextMemory. The evaluator then
    measures whether the newly introduced relation is immediately available and
    whether previously learned relations remain top-1 afterwards.
    """

    def __init__(self, radius: int = 3):
        self.memory = TextContextMemory(radius=radius)
        self.learned_pairs: list[tuple[str, str]] = []
        self.observations = 0

    def _is_top1_partner(self, query: str, target: str) -> bool:
        ranked = self.memory.nearest(query, top_k=1)
        return bool(ranked and ranked[0][0] == target)

    def _pair_accuracy(self, pairs: list[tuple[str, str]]) -> float:
        if not pairs:
            return 1.0
        checks = []
        for a, b in pairs:
            checks.append(self._is_top1_partner(a, b))
            checks.append(self._is_top1_partner(b, a))
        return sum(checks) / len(checks)

    def observe_batch(
        self,
        sentences: list[str],
        expected_pair: tuple[str, str],
    ) -> OnlineStep:
        before_pairs = list(self.learned_pairs)
        start = perf_counter()
        self.memory.observe_many(sentences)
        elapsed = perf_counter() - start
        self.observations += len(sentences)

        immediate = self._pair_accuracy([expected_pair])
        retention = self._pair_accuracy(before_pairs)
        self.learned_pairs.append(expected_pair)

        return OnlineStep(
            step=len(self.learned_pairs),
            observations=self.observations,
            update_seconds=elapsed,
            immediate_top1=immediate,
            retention_top1=retention,
        )
