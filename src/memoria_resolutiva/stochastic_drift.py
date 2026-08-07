from __future__ import annotations

from dataclasses import dataclass
from math import exp
from random import Random
from statistics import mean, pstdev


@dataclass(frozen=True, slots=True)
class StochasticRun:
    seed: int
    expected_change_epoch: int | None
    detected_change_epoch: int | None
    detection_delay: int | None
    false_alarms: int


@dataclass(frozen=True, slots=True)
class StochasticSummary:
    runs: int
    correct_epoch_probability: float
    eventual_detection_probability: float
    mean_detection_delay: float | None
    std_detection_delay: float | None
    false_alarm_rate: float
    delayed_runs: int
    missed_runs: int


def simulate_stochastic_drift_once(
    seed: int,
    fractions: tuple[float, ...] = (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
    *,
    samples_per_epoch: int = 100,
    decay: float = 0.9,
) -> StochasticRun:
    """Simulate noisy gradual drift using binomial sampling at every epoch.

    Each nominal fraction is a probability, not an exact count. The observed number
    of new-relation samples therefore fluctuates independently for every seed.
    Detection uses the same exponential recency rule as TemporalRelationMemory.
    """
    if samples_per_epoch < 1:
        raise ValueError("samples_per_epoch must be >= 1")
    if not 0.0 < decay <= 1.0:
        raise ValueError("decay must be in (0, 1]")
    if any(not 0.0 <= f <= 1.0 for f in fractions):
        raise ValueError("fractions must be in [0, 1]")

    rng = Random(seed)
    expected = next((i for i, f in enumerate(fractions) if f > 0.5), None)
    observations: list[tuple[int, int]] = []
    detected: int | None = None
    false_alarms = 0

    for epoch, fraction in enumerate(fractions):
        new_count = sum(rng.random() < fraction for _ in range(samples_per_epoch))
        old_count = samples_per_epoch - new_count
        observations.append((old_count, new_count))

        total_weight = 0.0
        old_score = 0.0
        new_score = 0.0
        for idx, (old_n, new_n) in enumerate(observations):
            weight = exp(-decay * (epoch - idx))
            total_weight += weight
            old_score += weight * old_n
            new_score += weight * new_n
        old_score /= total_weight
        new_score /= total_weight

        if new_score > old_score and detected is None:
            if expected is not None and epoch < expected:
                false_alarms += 1
            else:
                detected = epoch

    delay = None if expected is None or detected is None else detected - expected
    return StochasticRun(seed, expected, detected, delay, false_alarms)


def evaluate_stochastic_drift(
    runs: int = 1000,
    fractions: tuple[float, ...] = (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
    *,
    samples_per_epoch: int = 100,
    decay: float = 0.9,
    seed_start: int = 0,
) -> tuple[StochasticSummary, tuple[StochasticRun, ...]]:
    if runs < 1:
        raise ValueError("runs must be >= 1")

    results = tuple(
        simulate_stochastic_drift_once(
            seed_start + i,
            fractions,
            samples_per_epoch=samples_per_epoch,
            decay=decay,
        )
        for i in range(runs)
    )

    detected = [r for r in results if r.detected_change_epoch is not None]
    exact = [
        r for r in results
        if r.expected_change_epoch is not None
        and r.detected_change_epoch == r.expected_change_epoch
    ]
    delays = [r.detection_delay for r in results if r.detection_delay is not None]
    false_alarm_runs = sum(1 for r in results if r.false_alarms > 0)
    missed = runs - len(detected)
    delayed = sum(1 for d in delays if d > 0)

    summary = StochasticSummary(
        runs=runs,
        correct_epoch_probability=len(exact) / runs,
        eventual_detection_probability=len(detected) / runs,
        mean_detection_delay=mean(delays) if delays else None,
        std_detection_delay=pstdev(delays) if delays else None,
        false_alarm_rate=false_alarm_runs / runs,
        delayed_runs=delayed,
        missed_runs=missed,
    )
    return summary, results
