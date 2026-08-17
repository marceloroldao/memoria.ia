from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable


@dataclass(slots=True)
class LayerState:
    level: int
    strength: float = 0.0
    active: bool = False
    ever_active: bool = False
    history: list[tuple[int, str, float]] = field(default_factory=list)


class MemoryLifecycle:
    """Integrated multi-layer lifecycle with layer-local clocks.

    Evidence enters L0 immediately. Deeper layers accumulate more slowly using
    d_tau/dt = 2^-L and can activate only after the previous layer has activated.
    Contradiction weakens active memory with the same layer-local time law.
    Historical activation is retained even after functional deactivation.
    """

    def __init__(self, levels: int = 4, activate_threshold: float = 1.0, deactivate_threshold: float = 0.25):
        self.levels = levels
        self.activate_threshold = activate_threshold
        self.deactivate_threshold = deactivate_threshold
        self.time = 0
        self._items: dict[Hashable, list[LayerState]] = {}

    def _states(self, item: Hashable) -> list[LayerState]:
        return self._items.setdefault(item, [LayerState(i) for i in range(self.levels)])

    @staticmethod
    def rate(level: int) -> float:
        return 2.0 ** (-level)

    def support(self, item: Hashable, amount: float = 1.0) -> None:
        self.time += 1
        states = self._states(item)
        for i, state in enumerate(states):
            if i > 0 and not states[i - 1].ever_active:
                break
            state.strength += amount * self.rate(i)
            if not state.active and state.strength >= self.activate_threshold:
                state.active = True
                state.ever_active = True
                state.history.append((self.time, "activate", state.strength))
            else:
                state.history.append((self.time, "support", state.strength))

    def contradict(self, item: Hashable, amount: float = 1.0) -> None:
        self.time += 1
        states = self._states(item)
        for state in states:
            state.strength = max(0.0, state.strength - amount * self.rate(state.level))
            if state.active and state.strength <= self.deactivate_threshold:
                state.active = False
                state.history.append((self.time, "deactivate", state.strength))
            else:
                state.history.append((self.time, "contradict", state.strength))

    def active_depth(self, item: Hashable) -> int:
        states = self._states(item)
        active = [s.level for s in states if s.active]
        return max(active) if active else -1

    def historical_depth(self, item: Hashable) -> int:
        states = self._states(item)
        seen = [s.level for s in states if s.ever_active]
        return max(seen) if seen else -1

    def snapshot(self, item: Hashable) -> tuple[tuple[int, float, bool, bool], ...]:
        return tuple((s.level, s.strength, s.active, s.ever_active) for s in self._states(item))
