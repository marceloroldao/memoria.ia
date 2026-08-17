from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable

from .baseline_benchmark import HashMemory
from .packed_lifecycle import PackedMemoryLifecycle


class DecayMemory:
    """Simple online baseline with exponential forgetting."""
    def __init__(self, decay: float = 0.98):
        if not 0.0 < decay <= 1.0:
            raise ValueError("decay must be in (0, 1]")
        self.decay = decay
        self.data: dict[Hashable, float] = {}

    def _fade(self, key: Hashable) -> None:
        if key in self.data:
            self.data[key] *= self.decay

    def support(self, key: Hashable, amount: float = 1.0) -> None:
        self._fade(key)
        self.data[key] = self.data.get(key, 0.0) + amount

    def contradict(self, key: Hashable, amount: float = 1.0) -> None:
        self._fade(key)
        self.data[key] = max(0.0, self.data.get(key, 0.0) - amount)

    def active(self, key: Hashable) -> bool:
        return self.data.get(key, 0.0) > 0.0


@dataclass(frozen=True, slots=True)
class ContinualMetrics:
    name: str
    online_accuracy: float
    post_shift_accuracy: float
    deactivation_steps: int
    reactivation_steps: int
    retained_history: bool
    reactivated_old_regime: bool


def _active(memory, key: Hashable) -> bool:
    if isinstance(memory, HashMemory):
        return memory.data.get(key, 0.0) > 0.0
    if isinstance(memory, DecayMemory):
        return memory.active(key)
    if isinstance(memory, PackedMemoryLifecycle):
        return memory.active_depth(key) >= 0
    raise TypeError(type(memory))


def _historical(memory, key: Hashable) -> bool:
    if isinstance(memory, PackedMemoryLifecycle):
        return memory.historical_depth(key) >= 0
    if isinstance(memory, HashMemory):
        return key in memory.data
    if isinstance(memory, DecayMemory):
        return key in memory.data
    return False


def evaluate_regime_switch(name: str, factory, stable_steps: int = 32, shift_steps: int = 32, return_steps: int = 32) -> ContinualMetrics:
    """Single-key active -> inactive -> active continual-learning probe.

    Prediction is measured before each update, so no system receives credit for
    seeing the current label before predicting it. The test measures how quickly
    established state deactivates under sustained contradiction and how quickly
    it reactivates when the old regime returns.
    """
    m = factory()
    key = "concept"
    labels = [True] * stable_steps + [False] * shift_steps + [True] * return_steps
    correct = 0
    post_shift_correct = 0
    deactivation_steps = shift_steps
    reactivation_steps = return_steps
    deactivated = False
    reactivated = False

    for i, target_active in enumerate(labels):
        pred = _active(m, key)
        if pred == target_active:
            correct += 1
            if i >= stable_steps:
                post_shift_correct += 1

        if stable_steps <= i < stable_steps + shift_steps and not deactivated and not pred:
            deactivation_steps = i - stable_steps
            deactivated = True
        if i >= stable_steps + shift_steps and not reactivated and pred:
            reactivation_steps = i - (stable_steps + shift_steps)
            reactivated = True

        if target_active:
            m.support(key)
        else:
            m.contradict(key)

    retained = _historical(m, key)
    return ContinualMetrics(
        name=name,
        online_accuracy=correct / len(labels),
        post_shift_accuracy=post_shift_correct / (shift_steps + return_steps),
        deactivation_steps=deactivation_steps,
        reactivation_steps=reactivation_steps,
        retained_history=retained,
        reactivated_old_regime=_active(m, key) and retained,
    )


def default_factories():
    return {
        "hash": HashMemory,
        "decay_098": lambda: DecayMemory(0.98),
        "resolutive_packed": lambda: PackedMemoryLifecycle(levels=5),
    }
