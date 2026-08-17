from random import Random

from memoria_resolutiva.baseline_benchmark import HashMemory, ChronologicalMemory, benchmark
from memoria_resolutiva.memory_lifecycle import MemoryLifecycle


def make_events(n: int, items: int = 1000, seed: int = 57):
    rng = Random(seed)
    out = []
    for i in range(n):
        key = f"item_{rng.randrange(items)}"
        # Mostly support, with deterministic regime pockets of contradiction.
        phase = (i // max(1, n // 10)) % 4
        positive = phase != 2 if rng.random() < 0.85 else phase == 2
        out.append((key, positive, 1.0))
    return out


def main():
    for n in (10_000, 100_000):
        events = make_events(n)
        rows = [
            benchmark("hash", HashMemory(), events),
            benchmark("chronological", ChronologicalMemory(), events),
            benchmark("resolutive_lifecycle", MemoryLifecycle(levels=5), events),
        ]
        print("\nevents", n)
        for r in rows:
            print(r)


if __name__ == "__main__":
    main()
