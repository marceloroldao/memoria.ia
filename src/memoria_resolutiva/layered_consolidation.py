from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Hashable


@dataclass(frozen=True, slots=True)
class LayerState:
    layer: int
    resolution_bits: int
    proper_time: float
    accepted: frozenset[Hashable]


class LayeredConsolidationMemory:
    """Clock-gated multiscale consolidation without neural training.

    Layer 0 is immediately plastic. Higher layers advance more slowly and accept
    an item only when the evidence has persisted long enough in that layer's own
    proper time. Transient evidence can therefore remain shallow and disappear
    before becoming deeply consolidated.
    """

    def __init__(self, layers: int = 5, base_bits: int = 8, persistence_threshold: float = 2.0, decay_per_global_step: float = 0.15):
        if layers <= 0 or base_bits <= 0 or persistence_threshold <= 0:
            raise ValueError("invalid configuration")
        self.layers = layers
        self.base_bits = base_bits
        self.persistence_threshold = persistence_threshold
        self.decay_per_global_step = decay_per_global_step
        self.global_time = 0.0
        self.proper_time = [0.0 for _ in range(layers)]
        self._support = [defaultdict(float) for _ in range(layers)]
        self._accepted = [set() for _ in range(layers)]

    def resolution_bits(self, layer: int) -> int:
        return self.base_bits * (2 ** layer)

    def clock_rate(self, layer: int) -> float:
        return 2.0 ** (-layer)

    def _decay(self, dt: float) -> None:
        factor = max(0.0, 1.0 - self.decay_per_global_step * dt)
        for layer in range(self.layers):
            for key in list(self._support[layer]):
                self._support[layer][key] *= factor
                if self._support[layer][key] < 1e-9:
                    del self._support[layer][key]

    def observe(self, item: Hashable, weight: float = 1.0, dt: float = 1.0) -> None:
        if weight <= 0 or dt <= 0:
            raise ValueError("weight and dt must be positive")
        self._decay(dt)
        self.global_time += dt
        for layer in range(self.layers):
            d_tau = dt * self.clock_rate(layer)
            self.proper_time[layer] += d_tau
            self._support[layer][item] += weight * d_tau
            if layer == 0:
                self._accepted[layer].add(item)
            else:
                parent_ready = item in self._accepted[layer - 1]
                if parent_ready and self._support[layer][item] >= self.persistence_threshold:
                    self._accepted[layer].add(item)

    def advance_without_observation(self, dt: float = 1.0) -> None:
        if dt <= 0:
            raise ValueError("dt must be positive")
        self._decay(dt)
        self.global_time += dt
        for layer in range(self.layers):
            self.proper_time[layer] += dt * self.clock_rate(layer)

    def accepted_layers(self, item: Hashable) -> tuple[int, ...]:
        return tuple(layer for layer in range(self.layers) if item in self._accepted[layer])

    def state(self) -> list[LayerState]:
        return [
            LayerState(layer, self.resolution_bits(layer), self.proper_time[layer], frozenset(self._accepted[layer]))
            for layer in range(self.layers)
        ]
