from __future__ import annotations

from random import Random

from memoria_resolutiva.baseline_benchmark import benchmark
from memoria_resolutiva.compact_lifecycle import CompactMemoryLifecycle
from memoria_resolutiva.memory_lifecycle import MemoryLifecycle


def make_events(n: int, items: int, seed: int = 57):
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
        "full_lifecycle": lambda: MemoryLifecycle(levels=5),
        "compact_lifecycle": lambda: CompactMemoryLifecycle(levels=5),
    }
    for n, items in ((10_000, 1_000), (100_000, 5_000)):
        events = make_events(n, items)
        print(f"\nscale events={n} items={items}")
        for name, factory in factories.items():
            result = benchmark(name, factory(), events)
            print(result)


if __name__ == "__main__":
    main()
