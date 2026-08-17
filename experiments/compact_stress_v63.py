from __future__ import annotations

from random import Random
from time import perf_counter
import tracemalloc

from memoria_resolutiva.compact_lifecycle import CompactMemoryLifecycle


def make_events(n: int, items: int, seed: int = 63):
    rng = Random(seed)
    for i in range(n):
        key = f"item_{rng.randrange(items)}"
        phase = (i // max(1, n // 10)) % 4
        positive = phase != 2 if rng.random() < 0.85 else phase == 2
        yield key, positive, 1.0


def benchmark(events: int = 1_000_000, items: int = 20_000, seed: int = 63):
    memory = CompactMemoryLifecycle(levels=5)
    tracemalloc.start()
    start = perf_counter()
    for key, positive, amount in make_events(events, items, seed):
        if positive:
            memory.support(key, amount)
        else:
            memory.contradict(key, amount)
    elapsed = perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    transitions = sum(memory.transition_count(key) for key in memory._items)
    return {
        "events": events,
        "items": items,
        "seconds": elapsed,
        "latency_us": elapsed / events * 1e6,
        "throughput": events / elapsed,
        "peak_bytes": peak,
        "stored_items": len(memory._items),
        "transitions": transitions,
    }


def functional_probe():
    memory = CompactMemoryLifecycle(levels=5)
    for _ in range(32):
        memory.support("target")
    consolidated = (memory.active_depth("target"), memory.historical_depth("target"))

    for _ in range(40):
        memory.contradict("target")
    deconsolidated = (memory.active_depth("target"), memory.historical_depth("target"))

    for _ in range(32):
        memory.support("target")
    reactivated = (memory.active_depth("target"), memory.historical_depth("target"))

    return {
        "consolidated": consolidated,
        "deconsolidated": deconsolidated,
        "reactivated": reactivated,
        "transition_count": memory.transition_count("target"),
        "snapshot": memory.snapshot("target"),
    }


if __name__ == "__main__":
    print(benchmark())
    print(functional_probe())
