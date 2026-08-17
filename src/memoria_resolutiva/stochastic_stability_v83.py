from __future__ import annotations

from dataclasses import dataclass
from random import Random
from statistics import mean, stdev

from .saturating_lifecycle import SaturatingMemoryLifecycle


@dataclass(frozen=True, slots=True)
class StochasticResult:
    max_strength: float
    seeds: int
    noise_survival_mean: float
    noise_survival_sd: float
    switch_accuracy_mean: float
    switch_accuracy_sd: float
    history_retention_rate: float
    final_reactivation_rate: float


def _active(m: SaturatingMemoryLifecycle, key: str) -> bool:
    return m.active_depth(key) >= 0


def run_seed(max_strength: float, seed: int, steps: int = 400, noise_p: float = 0.08):
    rng = Random(seed)
    m = SaturatingMemoryLifecycle(levels=5, max_strength=max_strength)
    key = "concept"

    # Consolidate the initial regime.
    for _ in range(32):
        m.support(key)
    history_ok = m.historical_depth(key) >= 0

    # Short stochastic noise around a stable active regime.
    survived = 0
    for _ in range(steps // 2):
        if rng.random() < noise_p:
            m.contradict(key)
        else:
            m.support(key)
        survived += 1 if _active(m, key) else 0

    # Persistent regime switch with observation noise.
    correct = 0
    switch_steps = steps // 4
    for _ in range(switch_steps):
        target_active = False
        pred = _active(m, key)
        correct += 1 if pred == target_active else 0
        if rng.random() < noise_p:
            m.support(key)
        else:
            m.contradict(key)

    # Return to old regime with observation noise.
    for _ in range(switch_steps):
        target_active = True
        pred = _active(m, key)
        correct += 1 if pred == target_active else 0
        if rng.random() < noise_p:
            m.contradict(key)
        else:
            m.support(key)

    return (
        survived / (steps // 2),
        correct / (2 * switch_steps),
        history_ok and m.historical_depth(key) >= 0,
        _active(m, key),
    )


def evaluate(max_strength: float, seeds=(11, 23, 37, 57, 83, 101, 149, 211), noise_p: float = 0.08):
    rows = [run_seed(max_strength, seed, noise_p=noise_p) for seed in seeds]
    survival = [r[0] for r in rows]
    accuracy = [r[1] for r in rows]
    history = [1.0 if r[2] else 0.0 for r in rows]
    react = [1.0 if r[3] else 0.0 for r in rows]
    return StochasticResult(
        max_strength=max_strength,
        seeds=len(seeds),
        noise_survival_mean=mean(survival),
        noise_survival_sd=stdev(survival) if len(survival) > 1 else 0.0,
        switch_accuracy_mean=mean(accuracy),
        switch_accuracy_sd=stdev(accuracy) if len(accuracy) > 1 else 0.0,
        history_retention_rate=mean(history),
        final_reactivation_rate=mean(react),
    )
