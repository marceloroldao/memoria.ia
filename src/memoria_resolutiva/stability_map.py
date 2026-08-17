from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .stochastic_drift import evaluate_stochastic_drift


@dataclass(frozen=True, slots=True)
class StabilityPoint:
    profile: str
    samples_per_epoch: int
    decay: float
    noise: float
    detection_rate: float
    exact_detection_rate: float
    mean_delay: float | None
    std_delay: float | None
    false_alarm_rate: float


DRIFT_PROFILES: dict[str, tuple[float, ...]] = {
    "slow": (0.0, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 0.9, 1.0),
    "medium": (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
    "fast": (0.0, 0.2, 0.6, 0.9, 1.0),
}


def build_stability_map(
    *,
    seeds: int = 300,
    sample_grid: tuple[int, ...] = (10, 30, 100),
    decay_grid: tuple[float, ...] = (0.3, 0.9, 1.5),
    noise_grid: tuple[float, ...] = (0.0, 0.1, 0.25),
) -> tuple[StabilityPoint, ...]:
    """Sweep stochastic gradual-drift regimes.

    `noise` mixes each target fraction toward 0.5 before sampling, so larger values
    make old/new evidence less separable. Results are protocol-specific and expose
    the latency/noise trade-off instead of selecting a universal parameter.
    """
    points: list[StabilityPoint] = []
    for profile, fractions in DRIFT_PROFILES.items():
        for samples, decay, noise in product(sample_grid, decay_grid, noise_grid):
            summary, _runs = evaluate_stochastic_drift(
                runs=seeds,
                fractions=fractions,
                samples_per_epoch=samples,
                decay=decay,
                noise=noise,
            )
            points.append(
                StabilityPoint(
                    profile=profile,
                    samples_per_epoch=samples,
                    decay=decay,
                    noise=noise,
                    detection_rate=summary.eventual_detection_probability,
                    exact_detection_rate=summary.correct_epoch_probability,
                    mean_delay=summary.mean_detection_delay,
                    std_delay=summary.std_detection_delay,
                    false_alarm_rate=summary.false_alarm_rate,
                )
            )
    return tuple(points)


def robust_points(
    points: tuple[StabilityPoint, ...],
    *,
    min_exact: float = 0.95,
    max_false_alarm: float = 0.05,
    max_mean_delay: float = 0.25,
) -> tuple[StabilityPoint, ...]:
    """Return operating points satisfying explicit robustness thresholds."""
    return tuple(
        p
        for p in points
        if p.exact_detection_rate >= min_exact
        and p.false_alarm_rate <= max_false_alarm
        and p.mean_delay is not None
        and p.mean_delay <= max_mean_delay
    )
