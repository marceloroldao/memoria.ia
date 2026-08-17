from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class _Bin:
    positives: float = 1.0
    negatives: float = 1.0

    @property
    def probability(self) -> float:
        return self.positives / (self.positives + self.negatives)


class OnlineHistogramCalibrator:
    """Incremental, non-neural calibration of raw probabilities.

    Each resolved historical decision updates only one probability bin. The
    calibrator can therefore learn online without replaying the full history.
    Laplace priors prevent extreme confidence from tiny samples.
    """

    def __init__(self, bins: int = 20):
        if bins <= 1:
            raise ValueError("bins must be > 1")
        self.bins = bins
        self._data = [_Bin() for _ in range(bins)]

    def _index(self, p: float) -> int:
        if not 0.0 <= p <= 1.0:
            raise ValueError("probability must be in [0,1]")
        return min(self.bins - 1, int(p * self.bins))

    def update(self, raw_probability: float, outcome: int, weight: float = 1.0) -> None:
        if outcome not in (0, 1):
            raise ValueError("outcome must be binary")
        if weight <= 0:
            raise ValueError("weight must be positive")
        bucket = self._data[self._index(raw_probability)]
        if outcome:
            bucket.positives += weight
        else:
            bucket.negatives += weight

    def calibrate(self, raw_probability: float, min_count: float = 8.0) -> float:
        idx = self._index(raw_probability)
        bucket = self._data[idx]
        count = bucket.positives + bucket.negatives - 2.0
        if count < min_count:
            return raw_probability
        return bucket.probability

    def counts(self) -> list[float]:
        return [b.positives + b.negatives - 2.0 for b in self._data]
