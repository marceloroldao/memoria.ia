from __future__ import annotations

from dataclasses import dataclass
from random import Random
from time import perf_counter
import tracemalloc

from .memory_lifecycle import MemoryLifecycle


@dataclass(frozen=True, slots=True)
class StressMetrics:
    events: int
    items: int
    elapsed_s: float
    mean_latency_us: float
    peak_memory_mb: float
    mean_active_depth: float
    mean_historical_depth: float


def run_stress(events: int = 100_000, items: int = 5_000, seed: int = 12345) -> StressMetrics:
    rng = Random(seed)
    mem = MemoryLifecycle(levels=5)
    tracemalloc.start()
    start = perf_counter()
    for i in range(events):
        key = f"item_{rng.randrange(items)}"
        phase = (i // max(1, events // 5)) % 5
        r = rng.random()
        # Persistent regimes, transient noise, contradiction and recurrence.
        if phase in (0, 4):
            amount = 1.0 if r < 0.85 else 0.25
            mem.support(key, amount)
        elif phase == 1:
            if r < 0.55:
                mem.support(key, 0.5)
            else:
                mem.contradict(key, 0.25)
        elif phase == 2:
            if r < 0.75:
                mem.contradict(key, 1.0)
            else:
                mem.support(key, 0.25)
        else:
            if r < 0.50:
                mem.support(key, 1.0)
            else:
                mem.contradict(key, 1.0)
    elapsed = perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    active = []
    historical = []
    for idx in range(items):
        key = f"item_{idx}"
        active.append(mem.active_depth(key))
        historical.append(mem.historical_depth(key))

    return StressMetrics(
        events=events,
        items=items,
        elapsed_s=elapsed,
        mean_latency_us=(elapsed / events) * 1_000_000.0,
        peak_memory_mb=peak / (1024.0 * 1024.0),
        mean_active_depth=sum(active) / len(active),
        mean_historical_depth=sum(historical) / len(historical),
    )
