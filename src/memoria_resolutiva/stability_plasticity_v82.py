from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from .online_continual_v80 import ContinualMetrics, evaluate_regime_switch
from .saturating_lifecycle_v81 import SaturatingMemoryLifecycle


@dataclass(frozen=True, slots=True)
class FrontierPoint:
    max_strength: float
    noise_survival: float
    shift_deactivation_mean: float
    return_reactivation_mean: float
    online_accuracy_mean: float
    retained_history_rate: float


def short_noise_survival(max_strength: float, support_steps: int = 32, noise_steps: int = 3) -> float:
    m = SaturatingMemoryLifecycle(levels=5, max_strength=max_strength)
    key = "concept"
    for _ in range(support_steps):
        m.support(key)
    before = m.active_depth(key) >= 0
    for _ in range(noise_steps):
        m.contradict(key)
    after = m.active_depth(key) >= 0
    return 1.0 if before and after else 0.0


def evaluate_frontier(max_strength: float, regimes: Iterable[tuple[int, int, int]]) -> FrontierPoint:
    rows: list[ContinualMetrics] = []
    for stable_steps, shift_steps, return_steps in regimes:
        rows.append(evaluate_regime_switch(
            f"sat_{max_strength}",
            lambda ms=max_strength: SaturatingMemoryLifecycle(levels=5, max_strength=ms),
            stable_steps=stable_steps,
            shift_steps=shift_steps,
            return_steps=return_steps,
        ))
    return FrontierPoint(
        max_strength=max_strength,
        noise_survival=short_noise_survival(max_strength),
        shift_deactivation_mean=mean(r.deactivation_steps for r in rows),
        return_reactivation_mean=mean(r.reactivation_steps for r in rows),
        online_accuracy_mean=mean(r.online_accuracy for r in rows),
        retained_history_rate=mean(1.0 if r.retained_history else 0.0 for r in rows),
    )


def sweep_frontier(strengths=(1.25, 1.5, 2.0, 3.0, 4.0)):
    regimes = ((16, 16, 16), (32, 32, 32), (64, 48, 32), (24, 8, 24))
    return [evaluate_frontier(s, regimes) for s in strengths]
