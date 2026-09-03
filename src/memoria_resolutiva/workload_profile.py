from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True, slots=True)
class WorkloadProfile:
    name: str
    recommended_strategy: str
    average_fraction: float
    peak_fraction: float
    oscillation_ratio: float


def _oscillation_ratio(values: list[float], boundary: float = 0.40) -> float:
    if len(values) < 2:
        return 0.0
    sides = [value >= boundary for value in values]
    switches = sum(a != b for a, b in zip(sides, sides[1:]))
    return switches / (len(sides) - 1)


def classify_workload(
    affected_fractions: Iterable[float],
    *,
    sparse_mean: float = 0.12,
    dense_mean: float = 0.55,
    burst_peak: float = 0.55,
    oscillation_threshold: float = 0.45,
) -> WorkloadProfile:
    values = [float(value) for value in affected_fractions]
    if not values:
        return WorkloadProfile("sparse", "incremental", 0.0, 0.0, 0.0)
    if any(value < 0.0 or value > 1.0 for value in values):
        raise ValueError("affected fractions must be in [0, 1]")

    average = sum(values) / len(values)
    peak = max(values)
    oscillation = _oscillation_ratio(values)

    if average >= dense_mean:
        return WorkloadProfile("near_global", "adaptive", average, peak, oscillation)
    if oscillation >= oscillation_threshold and peak >= 0.45:
        return WorkloadProfile("oscillating", "hysteresis", average, peak, oscillation)
    if peak >= burst_peak and average < dense_mean:
        return WorkloadProfile("burst", "adaptive", average, peak, oscillation)
    if average <= sparse_mean:
        return WorkloadProfile("sparse", "incremental", average, peak, oscillation)

    # Conservative middle ground: use density-aware adaptive recomputation.
    return WorkloadProfile("mixed", "adaptive", average, peak, oscillation)
