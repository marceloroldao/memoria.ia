from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True, slots=True)
class LayerClockState:
    layer: int
    resolution_bits: int
    density: float
    proper_time: float
    global_time: float
    updates: int


class LayerClock:
    """Maintain global causal time and slower layer-local proper time.

    Layer resolution follows R(L)=8*2^L. Density defaults to 2^L.
    The clock law controls d_tau/d_t and is intentionally pluggable so the
    retention/plasticity tradeoff can be benchmarked rather than assumed.
    """

    def __init__(self, layer: int, law: str = "exponential", alpha: float = 1.0):
        if layer < 0:
            raise ValueError("layer must be >= 0")
        if alpha <= 0:
            raise ValueError("alpha must be positive")
        if law not in {"exponential", "linear", "sqrt_density", "power"}:
            raise ValueError("unknown clock law")
        self.layer = layer
        self.law = law
        self.alpha = alpha
        self.resolution_bits = 8 * (2 ** layer)
        self.density = float(2 ** layer)
        self.global_time = 0.0
        self.proper_time = 0.0
        self.updates = 0

    def rate(self) -> float:
        if self.law == "exponential":
            return 2.0 ** (-self.layer)
        if self.law == "linear":
            return 1.0 / (self.layer + 1.0)
        if self.law == "sqrt_density":
            return 1.0 / math.sqrt(self.density)
        # generalized density power law
        return self.density ** (-self.alpha)

    def advance(self, delta_t: float = 1.0) -> LayerClockState:
        if delta_t < 0:
            raise ValueError("delta_t must be non-negative")
        self.global_time += delta_t
        self.proper_time += delta_t * self.rate()
        self.updates += 1
        return self.snapshot()

    def snapshot(self) -> LayerClockState:
        return LayerClockState(
            self.layer,
            self.resolution_bits,
            self.density,
            self.proper_time,
            self.global_time,
            self.updates,
        )


class MultiLayerClockSystem:
    def __init__(self, max_layer: int = 5, law: str = "exponential", alpha: float = 1.0):
        self.clocks = [LayerClock(i, law=law, alpha=alpha) for i in range(max_layer + 1)]

    def advance_all(self, delta_t: float = 1.0) -> list[LayerClockState]:
        return [clock.advance(delta_t) for clock in self.clocks]

    def snapshots(self) -> list[LayerClockState]:
        return [clock.snapshot() for clock in self.clocks]
