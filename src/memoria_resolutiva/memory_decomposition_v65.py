from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
import tracemalloc

from .compact_lifecycle import CompactMemoryLifecycle


@dataclass(frozen=True, slots=True)
class MemoryDecomposition:
    events: int
    items: int
    transitions: int
    seconds: float
    peak_bytes: int
    bytes_per_item: float
    bytes_per_transition: float


def run_workload(events, items: int, levels: int = 5) -> MemoryDecomposition:
    memory = CompactMemoryLifecycle(levels=levels)
    tracemalloc.start()
    start = perf_counter()
    for key, positive, amount in events:
        if positive:
            memory.support(key, amount)
        else:
            memory.contradict(key, amount)
    seconds = perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    transitions = sum(memory.transition_count(key) for key in memory._items)
    return MemoryDecomposition(
        events=len(events),
        items=items,
        transitions=transitions,
        seconds=seconds,
        peak_bytes=peak,
        bytes_per_item=peak / max(items, 1),
        bytes_per_transition=peak / max(transitions, 1),
    )
