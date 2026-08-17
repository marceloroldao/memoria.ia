from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from .polysemy import Sense, jaccard


@dataclass(frozen=True, slots=True)
class TrajectoryEvidence:
    contextual_overlap: float
    support_balance: float
    recurrence: float
    divergence: float
    merge_signal: float
    split_signal: float


def _signature(sense: Sense, top_k: int = 20) -> set[str]:
    return {token for token, _ in sense.contexts.most_common(top_k)}


def derive_trajectory_evidence(a: Sense, b: Sense) -> TrajectoryEvidence:
    """Derive merge/split evidence directly from two sense trajectories.

    No hand-labelled merge/split input is required. Signals are computed from
    contextual overlap, support symmetry, recurrence and contextual divergence.
    """
    sa, sb = _signature(a), _signature(b)
    overlap = jaccard(sa, sb)
    total = max(1, a.occurrences + b.occurrences)
    support_balance = 1.0 - abs(a.occurrences - b.occurrences) / total
    recurrence = min(1.0, sqrt(max(0, a.occurrences * b.occurrences)) / 5.0)
    divergence = 1.0 - overlap

    merge_signal = max(0.0, min(1.0, 0.60 * overlap + 0.20 * support_balance + 0.20 * recurrence))
    split_signal = max(0.0, min(1.0, 0.70 * divergence + 0.30 * (1.0 - support_balance)))
    return TrajectoryEvidence(overlap, support_balance, recurrence, divergence, merge_signal, split_signal)


@dataclass(slots=True)
class AutoConceptConfidence:
    merge_mass: float = 1.0
    split_mass: float = 1.0

    @property
    def merge_probability(self) -> float:
        return self.merge_mass / (self.merge_mass + self.split_mass)

    @property
    def state(self) -> str:
        p = self.merge_probability
        if p >= 0.67:
            return "merge"
        if p <= 0.33:
            return "split"
        return "uncertain"

    def update(self, evidence: TrajectoryEvidence, weight: float = 1.0) -> float:
        if weight <= 0:
            raise ValueError("weight must be positive")
        self.merge_mass += evidence.merge_signal * weight
        self.split_mass += evidence.split_signal * weight
        return self.merge_probability
