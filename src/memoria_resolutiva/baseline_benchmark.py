from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from time import perf_counter
import tracemalloc
from typing import Hashable, Iterable


class HashMemory:
    def __init__(self):
        self.data: dict[Hashable, float] = {}

    def support(self, key: Hashable, amount: float = 1.0) -> None:
        self.data[key] = self.data.get(key, 0.0) + amount

    def contradict(self, key: Hashable, amount: float = 1.0) -> None:
        self.data[key] = max(0.0, self.data.get(key, 0.0) - amount)


class ChronologicalMemory:
    def __init__(self):
        self.events: list[tuple[Hashable, bool, float]] = []

    def support(self, key: Hashable, amount: float = 1.0) -> None:
        self.events.append((key, True, amount))

    def contradict(self, key: Hashable, amount: float = 1.0) -> None:
        self.events.append((key, False, amount))

    def score(self, key: Hashable) -> float:
        value = 0.0
        for k, positive, amount in self.events:
            if k == key:
                value = max(0.0, value + (amount if positive else -amount))
        return value


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    name: str
    events: int
    seconds: float
    latency_us: float
    throughput: float
    peak_bytes: int


def benchmark(name: str, memory, events: Iterable[tuple[Hashable, bool, float]]) -> BenchmarkResult:
    sequence = list(events)
    tracemalloc.start()
    start = perf_counter()
    for key, positive, amount in sequence:
        if positive:
            memory.support(key, amount)
        else:
            memory.contradict(key, amount)
    elapsed = perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    n = len(sequence)
    return BenchmarkResult(name, n, elapsed, elapsed / max(1, n) * 1e6, n / max(elapsed, 1e-12), peak)
