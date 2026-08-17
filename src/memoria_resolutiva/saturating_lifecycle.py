from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable


@dataclass(slots=True)
class SaturatingLayerState:
    level: int
    strength: float = 0.0
    active: bool = False
    ever_active: bool = False
    activation_count: int = 0
    deactivation_count: int = 0


class SaturatingMemoryLifecycle:
    """Stable-name saturating lifecycle used by the v0.90 routed API."""

    def __init__(
        self,
        levels: int = 5,
        activate_threshold: float = 1.0,
        deactivate_threshold: float = 0.25,
        max_strength: float = 1.25,
    ):
        if levels <= 0:
            raise ValueError("levels must be positive")
        if max_strength <= activate_threshold:
            raise ValueError("max_strength must exceed activate_threshold")
        self.levels = levels
        self.activate_threshold = activate_threshold
        self.deactivate_threshold = deactivate_threshold
        self.max_strength = max_strength
        self.time = 0
        self._items: dict[Hashable, list[SaturatingLayerState]] = {}

    def _states(self, item: Hashable):
        return self._items.setdefault(
            item, [SaturatingLayerState(i) for i in range(self.levels)]
        )

    @staticmethod
    def rate(level: int) -> float:
        return 2.0 ** (-level)

    def support(self, item: Hashable, amount: float = 1.0) -> None:
        self.time += 1
        states = self._states(item)
        for i, state in enumerate(states):
            if i > 0 and not states[i - 1].ever_active:
                break
            state.strength = min(
                self.max_strength,
                state.strength + amount * self.rate(i),
            )
            if not state.active and state.strength >= self.activate_threshold:
                state.active = True
                state.ever_active = True
                state.activation_count += 1

    def contradict(self, item: Hashable, amount: float = 1.0) -> None:
        self.time += 1
        for state in self._states(item):
            state.strength = max(
                0.0,
                state.strength - amount * self.rate(state.level),
            )
            if state.active and state.strength <= self.deactivate_threshold:
                state.active = False
                state.deactivation_count += 1

    def active_depth(self, item: Hashable) -> int:
        active = [s.level for s in self._states(item) if s.active]
        return max(active) if active else -1

    def historical_depth(self, item: Hashable) -> int:
        seen = [s.level for s in self._states(item) if s.ever_active]
        return max(seen) if seen else -1

    def snapshot(self, item: Hashable):
        return tuple(
            (
                s.level,
                s.strength,
                s.active,
                s.ever_active,
                s.activation_count,
                s.deactivation_count,
            )
            for s in self._states(item)
        )
