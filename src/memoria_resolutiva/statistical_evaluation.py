from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean, stdev
from typing import Callable, Iterable

from .baseline_benchmark import ChronologicalMemory, HashMemory, benchmark
from .capability_cost import CostScore, utility_per_cost
from .measured_capability import measure_capabilities
from .memory_lifecycle import MemoryLifecycle


@dataclass(frozen=True, slots=True)
class StatisticalSummary:
    name: str
    events: int
    runs: int
    quality_mean: float
    quality_sd: float
    latency_us_mean: float
    latency_us_sd: float
    peak_bytes_mean: float
    peak_bytes_sd: float
    utility_mean: float
    utility_sd: float
    utility_ci95: float


def summarize(values: Iterable[float]) -> tuple[float, float, float]:
    xs = list(values)
    if not xs:
        raise ValueError("at least one value is required")
    mu = mean(xs)
    sd = stdev(xs) if len(xs) > 1 else 0.0
    ci95 = 1.96 * sd / sqrt(len(xs)) if len(xs) > 1 else 0.0
    return mu, sd, ci95


def evaluate_system(
    name: str,
    factory: Callable[[], object],
    event_sets: list[list[tuple[str, bool, float]]],
    latency_ref: float,
    memory_ref: float,
) -> StatisticalSummary:
    qualities: list[float] = []
    latencies: list[float] = []
    peaks: list[float] = []
    utilities: list[float] = []

    for events in event_sets:
        cap = measure_capabilities(factory).score
        result = benchmark(name, factory(), events)
        cost = CostScore(result.latency_us, result.peak_bytes)
        qualities.append(cap.quality)
        latencies.append(result.latency_us)
        peaks.append(float(result.peak_bytes))
        utilities.append(utility_per_cost(cap, cost, latency_ref, int(memory_ref)))

    q_mu, q_sd, _ = summarize(qualities)
    l_mu, l_sd, _ = summarize(latencies)
    p_mu, p_sd, _ = summarize(peaks)
    u_mu, u_sd, u_ci = summarize(utilities)
    return StatisticalSummary(
        name=name,
        events=len(event_sets[0]) if event_sets else 0,
        runs=len(event_sets),
        quality_mean=q_mu,
        quality_sd=q_sd,
        latency_us_mean=l_mu,
        latency_us_sd=l_sd,
        peak_bytes_mean=p_mu,
        peak_bytes_sd=p_sd,
        utility_mean=u_mu,
        utility_sd=u_sd,
        utility_ci95=u_ci,
    )


def default_factories():
    return {
        "hash": HashMemory,
        "chronological": ChronologicalMemory,
        "resolutive_lifecycle": lambda: MemoryLifecycle(levels=5),
    }
