from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable

from .baseline_benchmark import ChronologicalMemory, HashMemory
from .capability_cost import CapabilityScore
from .memory_lifecycle import MemoryLifecycle


@dataclass(frozen=True, slots=True)
class CapabilityMeasurement:
    retention: float
    noise_resistance: float
    regime_adaptation: float
    reactivation: float

    @property
    def score(self) -> CapabilityScore:
        return CapabilityScore(
            retention=self.retention,
            noise_resistance=self.noise_resistance,
            regime_adaptation=self.regime_adaptation,
            reactivation=self.reactivation,
        )


def _strength(memory, key: Hashable) -> float:
    if isinstance(memory, HashMemory):
        return float(memory.data.get(key, 0.0))
    if isinstance(memory, ChronologicalMemory):
        return float(memory.score(key))
    if isinstance(memory, MemoryLifecycle):
        snapshot = memory.snapshot(key)
        # Sum active strengths so the scalar remains comparable before/after
        # perturbation without pretending that layer depth equals confidence.
        return float(sum(strength for _, strength, active, _ in snapshot if active))
    raise TypeError(f"unsupported memory type: {type(memory)!r}")


def _remembered(memory, key: Hashable) -> bool:
    if isinstance(memory, MemoryLifecycle):
        return memory.active_depth(key) >= 0
    return _strength(memory, key) > 0.0


def _historically_known(memory, key: Hashable) -> bool:
    if isinstance(memory, MemoryLifecycle):
        return memory.historical_depth(key) >= 0
    if isinstance(memory, HashMemory):
        return key in memory.data
    if isinstance(memory, ChronologicalMemory):
        return any(k == key for k, _, _ in memory.events)
    raise TypeError(f"unsupported memory type: {type(memory)!r}")


def measure_capabilities(memory_factory) -> CapabilityMeasurement:
    """Measure four controlled capabilities without model-specific tuning.

    Each probe receives a fresh memory instance. Scores are binary or bounded
    fractions and deliberately conservative: they test observable behavior,
    not internal implementation claims.
    """

    # 1. Retention: stable evidence remains retrievable after unrelated traffic.
    m = memory_factory()
    for _ in range(16):
        m.support("target")
    for i in range(128):
        m.support(f"distractor-{i}")
    retention = 1.0 if _remembered(m, "target") else 0.0

    # 2. Noise resistance: a small contradictory burst should not erase a
    # strongly established memory.
    m = memory_factory()
    for _ in range(16):
        m.support("target")
    before = max(_strength(m, "target"), 1e-12)
    for _ in range(3):
        m.contradict("target")
    after = max(_strength(m, "target"), 0.0)
    noise_resistance = min(1.0, after / before)

    # 3. Regime adaptation: sustained contrary evidence should eventually
    # change the functional state rather than leaving old evidence immutable.
    m = memory_factory()
    for _ in range(8):
        m.support("target")
    for _ in range(16):
        m.contradict("target")
    regime_adaptation = 1.0 if not _remembered(m, "target") else 0.0

    # 4. Reactivation: after deactivation, coherent evidence can restore a
    # previously known item. Historical knowledge is checked separately from
    # current activation for lifecycle memories.
    m = memory_factory()
    for _ in range(8):
        m.support("target")
    for _ in range(16):
        m.contradict("target")
    known = _historically_known(m, "target")
    for _ in range(8):
        m.support("target")
    reactivation = 1.0 if known and _remembered(m, "target") else 0.0

    return CapabilityMeasurement(
        retention=retention,
        noise_resistance=noise_resistance,
        regime_adaptation=regime_adaptation,
        reactivation=reactivation,
    )
