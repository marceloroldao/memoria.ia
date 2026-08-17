from __future__ import annotations

from random import Random

from memoria_resolutiva.baseline_benchmark import ChronologicalMemory, HashMemory
from memoria_resolutiva.capability_frontier import benchmark_frontier
from memoria_resolutiva.memory_lifecycle import MemoryLifecycle


def make_events(n: int, items: int, seed: int):
    rng = Random(seed)
    out = []
    for i in range(n):
        key = f"item_{rng.randrange(items)}"
        phase = (i // max(1, n // 10)) % 4
        positive = phase != 2 if rng.random() < 0.85 else phase == 2
        out.append((key, positive, 1.0))
    return out


def main():
    factories = {
        "hash": HashMemory,
        "chronological": ChronologicalMemory,
        "resolutive_lifecycle": lambda: MemoryLifecycle(levels=5),
    }
    for events_n, items in ((10_000, 1_000), (100_000, 5_000)):
        events = make_events(events_n, items, seed=57)
        query_keys = [f"item_{i % items}" for i in range(10_000)]
        print(f"\nscale events={events_n} items={items}")
        for name, factory in factories.items():
            print(benchmark_frontier(name, factory, events, query_keys))


if __name__ == "__main__":
    main()
