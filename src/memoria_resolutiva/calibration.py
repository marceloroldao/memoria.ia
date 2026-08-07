from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CalibrationBin:
    lower: float
    upper: float
    count: int
    mean_confidence: float
    empirical_accuracy: float


def brier_score(confidences: list[float], outcomes: list[int]) -> float:
    if len(confidences) != len(outcomes) or not confidences:
        raise ValueError("confidences and outcomes must have equal non-zero length")
    return sum((p - y) ** 2 for p, y in zip(confidences, outcomes)) / len(outcomes)


def reliability_bins(confidences: list[float], outcomes: list[int], bins: int = 10) -> list[CalibrationBin]:
    if len(confidences) != len(outcomes) or not confidences:
        raise ValueError("confidences and outcomes must have equal non-zero length")
    if bins <= 0:
        raise ValueError("bins must be positive")
    groups: list[list[tuple[float, int]]] = [[] for _ in range(bins)]
    for p, y in zip(confidences, outcomes):
        if not 0.0 <= p <= 1.0 or y not in (0, 1):
            raise ValueError("probabilities must be in [0,1] and outcomes binary")
        idx = min(bins - 1, int(p * bins))
        groups[idx].append((p, y))
    result = []
    for i, group in enumerate(groups):
        if not group:
            continue
        result.append(CalibrationBin(
            lower=i / bins,
            upper=(i + 1) / bins,
            count=len(group),
            mean_confidence=sum(p for p, _ in group) / len(group),
            empirical_accuracy=sum(y for _, y in group) / len(group),
        ))
    return result


def expected_calibration_error(confidences: list[float], outcomes: list[int], bins: int = 10) -> float:
    rel = reliability_bins(confidences, outcomes, bins)
    n = len(confidences)
    return sum((b.count / n) * abs(b.mean_confidence - b.empirical_accuracy) for b in rel)
