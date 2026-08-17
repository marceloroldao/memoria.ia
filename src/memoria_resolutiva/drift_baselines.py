from __future__ import annotations

from dataclasses import dataclass
from math import exp
from random import Random
from statistics import mean


@dataclass(frozen=True, slots=True)
class DetectorRun:
    seed: int
    expected_epoch: int | None
    detected_epoch: int | None
    false_alarms: int

    @property
    def delay(self) -> int | None:
        if self.expected_epoch is None or self.detected_epoch is None:
            return None
        return self.detected_epoch - self.expected_epoch


@dataclass(frozen=True, slots=True)
class DetectorSummary:
    name: str
    runs: int
    exact_rate: float
    detection_rate: float
    false_alarm_rate: float
    mean_delay: float | None


def _effective_fraction(fraction: float, noise: float) -> float:
    return (1.0 - noise) * fraction + noise * 0.5


def sample_stream(
    seed: int,
    fractions: tuple[float, ...],
    *,
    samples_per_epoch: int,
    noise: float,
) -> tuple[float, ...]:
    rng = Random(seed)
    values: list[float] = []
    for fraction in fractions:
        p = _effective_fraction(fraction, noise)
        new_count = sum(rng.random() < p for _ in range(samples_per_epoch))
        values.append(new_count / samples_per_epoch)
    return tuple(values)


def _record_detection(
    epoch: int,
    score: float,
    expected: int | None,
    detected: int | None,
    false_alarms: int,
) -> tuple[int | None, int]:
    if score <= 0.5 or detected is not None:
        return detected, false_alarms
    if expected is not None and epoch < expected:
        return detected, false_alarms + 1
    return epoch, false_alarms


def resolutive_detector(
    values: tuple[float, ...],
    *,
    decay: float,
    expected: int | None,
    seed: int,
) -> DetectorRun:
    history: list[float] = []
    detected = None
    false_alarms = 0
    for epoch, value in enumerate(values):
        history.append(value)
        weights = [exp(-decay * (epoch - i)) for i in range(len(history))]
        score = sum(w * x for w, x in zip(weights, history)) / sum(weights)
        detected, false_alarms = _record_detection(
            epoch, score, expected, detected, false_alarms
        )
    return DetectorRun(seed, expected, detected, false_alarms)


def ewma_detector(
    values: tuple[float, ...],
    *,
    alpha: float,
    expected: int | None,
    seed: int,
) -> DetectorRun:
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be in (0, 1]")
    state: float | None = None
    detected = None
    false_alarms = 0
    for epoch, value in enumerate(values):
        state = value if state is None else alpha * value + (1.0 - alpha) * state
        detected, false_alarms = _record_detection(
            epoch, state, expected, detected, false_alarms
        )
    return DetectorRun(seed, expected, detected, false_alarms)


def cusum_detector(
    values: tuple[float, ...],
    *,
    reference: float = 0.03,
    threshold: float = 0.25,
    expected: int | None,
    seed: int,
) -> DetectorRun:
    cumulative = 0.0
    detected = None
    false_alarms = 0
    for epoch, value in enumerate(values):
        cumulative = max(0.0, cumulative + (value - 0.5) - reference)
        if cumulative > threshold and detected is None:
            if expected is not None and epoch < expected:
                false_alarms += 1
                cumulative = 0.0
            else:
                detected = epoch
    return DetectorRun(seed, expected, detected, false_alarms)


def _summarize(name: str, runs: tuple[DetectorRun, ...]) -> DetectorSummary:
    total = len(runs)
    detected = [r for r in runs if r.detected_epoch is not None]
    exact = [r for r in runs if r.detected_epoch == r.expected_epoch]
    delays = [r.delay for r in runs if r.delay is not None]
    return DetectorSummary(
        name=name,
        runs=total,
        exact_rate=len(exact) / total,
        detection_rate=len(detected) / total,
        false_alarm_rate=sum(r.false_alarms > 0 for r in runs) / total,
        mean_delay=mean(delays) if delays else None,
    )


def compare_detectors(
    *,
    seeds: int = 1000,
    fractions: tuple[float, ...] = (0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
    samples_per_epoch: int = 100,
    noise: float = 0.0,
    decay: float = 0.9,
    ewma_alpha: float | None = None,
    cusum_reference: float = 0.03,
    cusum_threshold: float = 0.25,
) -> tuple[DetectorSummary, DetectorSummary, DetectorSummary]:
    expected = next((i for i, f in enumerate(fractions) if f > 0.5), None)
    alpha = (1.0 - exp(-decay)) if ewma_alpha is None else ewma_alpha

    resolutive_runs: list[DetectorRun] = []
    ewma_runs: list[DetectorRun] = []
    cusum_runs: list[DetectorRun] = []
    for seed in range(seeds):
        values = sample_stream(
            seed,
            fractions,
            samples_per_epoch=samples_per_epoch,
            noise=noise,
        )
        resolutive_runs.append(
            resolutive_detector(values, decay=decay, expected=expected, seed=seed)
        )
        ewma_runs.append(
            ewma_detector(values, alpha=alpha, expected=expected, seed=seed)
        )
        cusum_runs.append(
            cusum_detector(
                values,
                reference=cusum_reference,
                threshold=cusum_threshold,
                expected=expected,
                seed=seed,
            )
        )

    return (
        _summarize("resolutive-exp", tuple(resolutive_runs)),
        _summarize("ewma", tuple(ewma_runs)),
        _summarize("cusum", tuple(cusum_runs)),
    )
