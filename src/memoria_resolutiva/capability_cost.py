from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CapabilityScore:
    retention: float
    noise_resistance: float
    regime_adaptation: float
    reactivation: float

    @property
    def quality(self) -> float:
        return (self.retention + self.noise_resistance + self.regime_adaptation + self.reactivation) / 4.0


@dataclass(frozen=True, slots=True)
class CostScore:
    latency_us: float
    peak_bytes: int


def normalized_cost(cost: CostScore, latency_ref: float, memory_ref: int) -> float:
    if latency_ref <= 0 or memory_ref <= 0:
        raise ValueError("references must be positive")
    return 0.5 * (cost.latency_us / latency_ref) + 0.5 * (cost.peak_bytes / memory_ref)


def utility_per_cost(capability: CapabilityScore, cost: CostScore, latency_ref: float, memory_ref: int) -> float:
    c = normalized_cost(cost, latency_ref, memory_ref)
    return capability.quality / max(c, 1e-12)
