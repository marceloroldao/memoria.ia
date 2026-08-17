from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable


@dataclass(slots=True)
class LayerState:
    layer: int
    active: bool = False
    strength: float = 0.0
    history: list[tuple[int, str, float]] = field(default_factory=list)


class DeconsolidationMemory:
    """Gradual loss of active influence without deleting historical memory."""

    def __init__(self, layers: int = 4, deactivate_threshold: float = 0.25):
        self.layers = layers
        self.deactivate_threshold = deactivate_threshold
        self.time = 0
        self._items: dict[Hashable, list[LayerState]] = {}

    def ensure(self, item: Hashable) -> list[LayerState]:
        if item not in self._items:
            self._items[item] = [LayerState(layer=i) for i in range(self.layers)]
        return self._items[item]

    def seed_consolidated(self, item: Hashable, strengths: list[float] | None = None) -> None:
        states = self.ensure(item)
        vals = strengths or [1.0] * self.layers
        for state, strength in zip(states, vals):
            state.active = strength >= self.deactivate_threshold
            state.strength = strength
            state.history.append((self.time, "seed", strength))

    def contradict(self, item: Hashable, amount: float = 0.1) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        self.time += 1
        states = self.ensure(item)
        # Deep layers change more slowly: penalty is scaled by 2^-L.
        for state in states:
            delta = amount * (2.0 ** (-state.layer))
            state.strength = max(0.0, state.strength - delta)
            if state.active and state.strength < self.deactivate_threshold:
                state.active = False
                event = "deactivate"
            else:
                event = "weaken"
            state.history.append((self.time, event, state.strength))

    def reinforce(self, item: Hashable, amount: float = 0.1) -> None:
        if amount < 0:
            raise ValueError("amount must be non-negative")
        self.time += 1
        states = self.ensure(item)
        for state in states:
            delta = amount * (2.0 ** (-state.layer))
            state.strength = min(1.0, state.strength + delta)
            if not state.active and state.strength >= self.deactivate_threshold:
                state.active = True
                event = "reactivate"
            else:
                event = "strengthen"
            state.history.append((self.time, event, state.strength))

    def active_layers(self, item: Hashable) -> list[int]:
        return [s.layer for s in self.ensure(item) if s.active]

    def snapshot(self, item: Hashable) -> list[dict]:
        return [
            {
                "layer": s.layer,
                "active": s.active,
                "strength": s.strength,
                "history": list(s.history),
            }
            for s in self.ensure(item)
        ]
