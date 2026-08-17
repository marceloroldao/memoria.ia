from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable


@dataclass(slots=True)
class CompactLayerState:
    level: int
    strength: float = 0.0
    active: bool = False
    ever_active: bool = False
    # Only state transitions are persisted. Ordinary support/contradict events
    # update strength in place and do not allocate history records.
    transitions: list[tuple[int, str, float]] = field(default_factory=list)


class CompactMemoryLifecycle:
    """Transition-only variant of MemoryLifecycle.

    It preserves current strength, activation state, historical activation and
    layer depth while intentionally discarding per-event provenance. This is a
    capability/cost ablation, not a replacement for the full provenance mode.
    """

    def __init__(self, levels: int = 4, activate_threshold: float = 1.0, deactivate_threshold: float = 0.25):
        self.levels = levels
        self.activate_threshold = activate_threshold
        self.deactivate_threshold = deactivate_threshold
        self.time = 0
        self._items: dict[Hashable, list[CompactLayerState]] = {}

    def _states(self, item: Hashable) -> list[CompactLayerState]:
        return self._items.setdefault(item, [CompactLayerState(i) for i in range(self.levels)])

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
                state.transitions.append((self.time, "activate", state.strength))

    def contradict(self, item: Hashable, amount: float = 1.0) -> None:
        self.time += 1
        states = self._states(item)
        for state in states:
            state.strength = max(0.0, state.strength - amount * self.rate(state.level))
            if state.active and state.strength <= self.deactivate_threshold:
                state.active = False
                state.transitions.append((self.time, "deactivate", state.strength))

    def active_depth(self, item: Hashable) -> int:
        active = [s.level for s in self._states(item) if s.active]
        return max(active) if active else -1

    def historical_depth(self, item: Hashable) -> int:
        seen = [s.level for s in self._states(item) if s.ever_active]
        return max(seen) if seen else -1

    def snapshot(self, item: Hashable) -> tuple[tuple[int, float, bool, bool], ...]:
        return tuple((s.level, s.strength, s.active, s.ever_active) for s in self._states(item))

    def transition_count(self, item: Hashable) -> int:
        return sum(len(s.transitions) for s in self._states(item))
