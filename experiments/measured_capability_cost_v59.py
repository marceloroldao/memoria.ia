from random import Random

from memoria_resolutiva.baseline_benchmark import HashMemory, ChronologicalMemory, benchmark
from memoria_resolutiva.capability_cost import CostScore, utility_per_cost
from memoria_resolutiva.measured_capability import measure_capabilities
from memoria_resolutiva.memory_lifecycle import MemoryLifecycle


def make_events(n: int, items: int = 1000, seed: int = 59):
    rng = Random(seed)
    events = []
    for i in range(n):
        key = f"item_{rng.randrange(items)}"
        phase = (i // max(1, n // 12)) % 4
        positive = phase != 2
        if rng.random() < 0.15:
            positive = not positive
        events.append((key, positive, 1.0))
    return events


def main():
    factories = {
        "hash": HashMemory,
        "chronological": ChronologicalMemory,
        "resolutive_lifecycle": lambda: MemoryLifecycle(levels=5),
    }

    events = make_events(100_000)
    rows = {}
    for name, factory in factories.items():
        capability = measure_capabilities(factory).score
        measured = benchmark(name, factory(), events)
        cost = CostScore(latency_us=measured.latency_us, peak_bytes=measured.peak_bytes)
        rows[name] = (capability, cost, measured)

    latency_ref = min(cost.latency_us for _, cost, _ in rows.values())
    memory_ref = min(cost.peak_bytes for _, cost, _ in rows.values())

    for name, (capability, cost, measured) in rows.items():
        print(
            name,
            "capabilities=",
            {
                "retention": round(capability.retention, 4),
                "noise_resistance": round(capability.noise_resistance, 4),
                "regime_adaptation": round(capability.regime_adaptation, 4),
                "reactivation": round(capability.reactivation, 4),
            },
            "quality=", round(capability.quality, 4),
            "latency_us=", round(cost.latency_us, 4),
            "peak_bytes=", cost.peak_bytes,
            "utility_per_cost=", round(
                utility_per_cost(capability, cost, latency_ref, memory_ref), 6
            ),
        )


if __name__ == "__main__":
    main()
