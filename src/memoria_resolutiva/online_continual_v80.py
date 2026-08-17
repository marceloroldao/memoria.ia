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
        self.data[key] = self.data.get(key, 0.0) - amount

    def predict(self, key: Hashable) -> int:
        return 1 if self.data.get(key, 0.0) >= 0.0 else -1


@dataclass(frozen=True, slots=True)
class ContinualMetrics:
    name: str
    online_accuracy: float
    post_shift_accuracy: float
    recovery_steps: int
    retained_old_regime: bool
    reactivated_old_regime: bool


def _predict(memory, key: Hashable) -> int:
    if isinstance(memory, HashMemory):
        return 1 if memory.data.get(key, 0.0) >= 0.0 else -1
    if isinstance(memory, DecayMemory):
        return memory.predict(key)
    if isinstance(memory, PackedMemoryLifecycle):
        states = memory.snapshot(key)
        active_strength = sum(strength for _, strength, active, _ in states if active)
        return 1 if active_strength > 0 else -1
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
    """Single-key A -> B -> A continual-learning probe.

    Labels are +1 in regime A and -1 in regime B. Prediction is measured before
    each update to avoid giving any system credit for seeing the answer first.
    """
    m = factory()
    key = "concept"
    labels = [1] * stable_steps + [-1] * shift_steps + [1] * return_steps
    correct = 0
    post_shift_correct = 0
    recovery_steps = shift_steps
    switched = False

    for i, y in enumerate(labels):
        pred = _predict(m, key)
        if pred == y:
            correct += 1
            if i >= stable_steps:
                post_shift_correct += 1
        if stable_steps <= i < stable_steps + shift_steps and not switched and pred == -1:
            recovery_steps = i - stable_steps
            switched = True
        if y > 0:
            m.support(key)
        else:
            m.contradict(key)

    retained = _historical(m, key)
    # After the final A return, resolutive history should still know the concept.
    reactivated = _predict(m, key) == 1 and retained
    return ContinualMetrics(
        name=name,
        online_accuracy=correct / len(labels),
        post_shift_accuracy=post_shift_correct / (shift_steps + return_steps),
        recovery_steps=recovery_steps,
        retained_old_regime=retained,
        reactivated_old_regime=reactivated,
    )


def default_factories():
    return {
        "hash": HashMemory,
        "decay_098": lambda: DecayMemory(0.98),
        "resolutive_packed": lambda: PackedMemoryLifecycle(levels=5),
    }
