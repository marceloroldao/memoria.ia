from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable


@dataclass(slots=True)
class PackedLayerState:
    level: int
    strength: float = 0.0
    active: bool = False
    ever_active: bool = False
    activation_count: int = 0
    deactivation_count: int = 0
    last_transition_time: int = 0
    last_transition_kind: int = 0  # 0 none, 1 activate, 2 deactivate
    last_transition_strength: float = 0.0

    @property
    def transition_count(self) -> int:
        return self.activation_count + self.deactivation_count


class PackedMemoryLifecycle:
    """Low-overhead operational lifecycle for memoria.ia v0.70.

    The state dynamics are intentionally identical to CompactMemoryLifecycle:
    layer-local rate r_L = 2^-L, gated deeper activation, deconsolidation and
    reactivation. Instead of retaining every transition tuple, each layer keeps
    transition counters plus only its most recent transition.

    This mode preserves functional state and transition counts, but not a full
    chronological audit trail. Full provenance remains a separate capability.
    """

    def __init__(self, levels: int = 4, activate_threshold: float = 1.0, deactivate_threshold: float = 0.25):
        self.levels = levels
        self.activate_threshold = activate_threshold
        self.deactivate_threshold = deactivate_threshold
        self.time = 0
        self._items: dict[Hashable, list[PackedLayerState]] = {}

    def _states(self, item: Hashable) -> list[PackedLayerState]:
        return self._items.setdefault(item, [PackedLayerState(i) for i in range(self.levels)])

    @staticmethod
    def rate(level: int) -> float:
        return 2.0 ** (-level)

    def _record(self, state: PackedLayerState, kind: int) -> None:
        if kind == 1:
            state.activation_count += 1
        else:
            state.deactivation_count += 1
        state.last_transition_time = self.time
        state.last_transition_kind = kind
        state.last_transition_strength = state.strength

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
                self._record(state, 1)

    def contradict(self, item: Hashable, amount: float = 1.0) -> None:
        self.time += 1
        states = self._states(item)
        for state in states:
            state.strength = max(0.0, state.strength - amount * self.rate(state.level))
            if state.active and state.strength <= self.deactivate_threshold:
                state.active = False
                self._record(state, 2)

    def active_depth(self, item: Hashable) -> int:
        active = [s.level for s in self._states(item) if s.active]
        return max(active) if active else -1

    def historical_depth(self, item: Hashable) -> int:
        seen = [s.level for s in self._states(item) if s.ever_active]
        return max(seen) if seen else -1

    def snapshot(self, item: Hashable) -> tuple[tuple[int, float, bool, bool], ...]:
        return tuple((s.level, s.strength, s.active, s.ever_active) for s in self._states(item))

    def transition_count(self, item: Hashable) -> int:
        return sum(s.transition_count for s in self._states(item))
