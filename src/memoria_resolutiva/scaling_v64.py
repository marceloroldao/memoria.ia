from __future__ import annotations

from dataclasses import dataclass
from math import log
from statistics import mean, stdev
from time import perf_counter
import tracemalloc

from .compact_lifecycle import CompactMemoryLifecycle


@dataclass(frozen=True, slots=True)
class ScalingPoint:
    events: int
    items: int
    runs: int
    latency_us_mean: float
    latency_us_sd: float
    throughput_mean: float
    peak_bytes_mean: float
    bytes_per_item: float


def run_once(events, memory_factory):
    m = memory_factory()
    tracemalloc.start()
    start = perf_counter()
    for key, positive, amount in events:
        (m.support if positive else m.contradict)(key, amount)
    elapsed = perf_counter() - start
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    n = len(events)
    return elapsed / n * 1e6, n / elapsed, peak


def evaluate_scale(event_sets, items: int, levels: int = 5) -> ScalingPoint:
    latencies, throughputs, peaks = [], [], []
    for events in event_sets:
        latency, throughput, peak = run_once(events, lambda: CompactMemoryLifecycle(levels=levels))
        latencies.append(latency)
        throughputs.append(throughput)
        peaks.append(float(peak))
    return ScalingPoint(
        events=len(event_sets[0]), items=items, runs=len(event_sets),
        latency_us_mean=mean(latencies),
        latency_us_sd=stdev(latencies) if len(latencies) > 1 else 0.0,
        throughput_mean=mean(throughputs),
        peak_bytes_mean=mean(peaks),
        bytes_per_item=mean(peaks) / items,
    )


def empirical_exponent(xs, ys) -> float:
    """Log-log least-squares exponent y ~ x^p."""
    lx = [log(float(x)) for x in xs]
    ly = [log(float(y)) for y in ys]
    mx, my = mean(lx), mean(ly)
    denom = sum((x - mx) ** 2 for x in lx)
    if denom == 0:
        raise ValueError("x values must vary")
    return sum((x - mx) * (y - my) for x, y in zip(lx, ly)) / denom
