from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(slots=True)
class SourceStats:
    confirmed: float = 0.0
    contradicted: float = 0.0

    @property
    def total(self) -> float:
        return self.confirmed + self.contradicted


class SourceReliabilityMemory:
    """Online source reliability learned from resolved historical claims.

    Uses a Beta prior so new sources do not start at confidence 0 or 1.
    Reliability is the posterior mean; Wilson lower bound is exposed as a
    conservative confidence estimate for diagnostics.
    """

    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        if prior_alpha <= 0 or prior_beta <= 0:
            raise ValueError("Beta prior parameters must be positive")
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self._stats: dict[str, SourceStats] = {}

    def _get(self, source: str) -> SourceStats:
        return self._stats.setdefault(source, SourceStats())

    def confirm(self, source: str, weight: float = 1.0) -> None:
        if weight <= 0:
            raise ValueError("weight must be positive")
        self._get(source).confirmed += weight

    def contradict(self, source: str, weight: float = 1.0) -> None:
        if weight <= 0:
            raise ValueError("weight must be positive")
        self._get(source).contradicted += weight

    def reliability(self, source: str) -> float:
        s = self._get(source)
        return (self.prior_alpha + s.confirmed) / (
            self.prior_alpha + self.prior_beta + s.total
        )

    def evidence_count(self, source: str) -> float:
        return self._get(source).total

    def wilson_lower(self, source: str, z: float = 1.96) -> float:
        s = self._get(source)
        n = s.total
        if n <= 0:
            return 0.0
        p = s.confirmed / n
        denom = 1.0 + z * z / n
        center = p + z * z / (2.0 * n)
        radius = z * sqrt((p * (1.0 - p) + z * z / (4.0 * n)) / n)
        return max(0.0, (center - radius) / denom)

    def snapshot(self) -> dict[str, dict[str, float]]:
        return {
            source: {
                "confirmed": stats.confirmed,
                "contradicted": stats.contradicted,
                "reliability": self.reliability(source),
                "wilson_lower": self.wilson_lower(source),
            }
            for source, stats in self._stats.items()
        }
