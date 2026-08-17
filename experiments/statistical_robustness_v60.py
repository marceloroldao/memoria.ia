from __future__ import annotations

from random import Random

from memoria_resolutiva.baseline_benchmark import benchmark
from memoria_resolutiva.capability_cost import CostScore
from memoria_resolutiva.statistical_evaluation import default_factories, evaluate_system


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
    seeds = [11, 23, 37, 57, 83, 101, 149, 211]
    scales = [(10_000, 1_000), (100_000, 5_000)]
    factories = default_factories()

    for events, items in scales:
        event_sets = [make_events(events, items, seed) for seed in seeds]

        # Reference cost is measured from the same workload family instead of
        # hard-coded. We use the lowest observed baseline cost components.
        reference_results = []
        for name, factory in factories.items():
            result = benchmark(name, factory(), event_sets[0])
            reference_results.append(result)
        latency_ref = min(r.latency_us for r in reference_results)
        memory_ref = min(r.peak_bytes for r in reference_results)

        print(f"\nscale events={events} items={items} seeds={len(seeds)}")
        for name, factory in factories.items():
            row = evaluate_system(
                name,
                factory,
                event_sets,
                latency_ref=latency_ref,
                memory_ref=memory_ref,
            )
            print(row)


if __name__ == "__main__":
    main()
