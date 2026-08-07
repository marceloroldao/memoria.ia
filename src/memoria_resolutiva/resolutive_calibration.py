from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from random import Random

from .calibration import brier_score, expected_calibration_error, reliability_bins
from .polysemy import Sense
from .trajectory_confidence import AutoConceptConfidence, derive_trajectory_evidence


@dataclass(frozen=True, slots=True)
class ResolutiveCalibrationResult:
    n: int
    accuracy: float
    brier: float
    ece: float
    min_confidence: float
    max_confidence: float


def _sense(tokens: set[str], occurrences: int, sense_id: int) -> Sense:
    return Sense(sense_id=sense_id, contexts=Counter({token: 1 for token in tokens}), occurrences=occurrences)


def synthetic_resolutive_trials(seed: int = 123, n: int = 5000) -> tuple[list[float], list[int]]:
    """Generate controlled merge/split pairs with known latent class.

    Merge pairs share substantial context; split pairs share little context.
    The label is used only for evaluation, not by trajectory evidence.
    """
    rng = Random(seed)
    vocabulary = [f"t{i}" for i in range(100)]
    confidences: list[float] = []
    outcomes: list[int] = []

    for _ in range(n):
        truth = rng.choice((0, 1))
        base = set(rng.sample(vocabulary, rng.randint(6, 12)))
        keep = rng.uniform(0.55, 0.95) if truth else rng.uniform(0.0, 0.25)
        common_n = min(len(base), int(len(base) * keep))
        common = set(rng.sample(list(base), common_n)) if common_n else set()

        target_size = max(len(common), max(4, len(base) + rng.randint(-2, 2)))
        candidates = [token for token in vocabulary if token not in common]
        extra_n = max(0, min(len(candidates), target_size - len(common)))
        other = common | set(rng.sample(candidates, extra_n))

        a = _sense(base, rng.randint(2, 12), 0)
        b = _sense(other, rng.randint(2, 12), 1)
        evidence = derive_trajectory_evidence(a, b)
        confidence = AutoConceptConfidence()
        confidence.update(evidence)
        confidences.append(confidence.merge_probability)
        outcomes.append(truth)

    return confidences, outcomes


def evaluate_resolutive_calibration(seed: int = 123, n: int = 5000, bins: int = 10) -> ResolutiveCalibrationResult:
    confidences, outcomes = synthetic_resolutive_trials(seed=seed, n=n)
    accuracy = sum((p >= 0.5) == bool(y) for p, y in zip(confidences, outcomes)) / n
    return ResolutiveCalibrationResult(
        n=n,
        accuracy=accuracy,
        brier=brier_score(confidences, outcomes),
        ece=expected_calibration_error(confidences, outcomes, bins=bins),
        min_confidence=min(confidences),
        max_confidence=max(confidences),
    )


def resolutive_reliability(seed: int = 123, n: int = 5000, bins: int = 10):
    confidences, outcomes = synthetic_resolutive_trials(seed=seed, n=n)
    return reliability_bins(confidences, outcomes, bins=bins)
