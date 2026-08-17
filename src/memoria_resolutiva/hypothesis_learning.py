from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable


@dataclass(slots=True)
class Hypothesis:
    hypothesis_id: int
    source: Hashable
    target: Hashable
    relation: Hashable
    value: Hashable
    prior_confidence: float
    confirmations: int = 0
    rejections: int = 0
    status: str = "pending"
    history: list[tuple[int, str, float]] = field(default_factory=list)

    @property
    def posterior_confidence(self) -> float:
        strength = 4.0
        a = max(1e-9, self.prior_confidence * strength) + self.confirmations
        b = max(1e-9, (1.0 - self.prior_confidence) * strength) + self.rejections
        return a / (a + b)


class HypothesisLearner:
    def __init__(self, support_threshold: float = 0.80, reject_threshold: float = 0.20):
        self.support_threshold = support_threshold
        self.reject_threshold = reject_threshold
        self._next_id = 1
        self.hypotheses: dict[int, Hypothesis] = {}
        self.facts: set[tuple[Hashable, Hashable, Hashable]] = set()
        self.time = 0

    def propose(self, source: Hashable, target: Hashable, relation: Hashable, value: Hashable, confidence: float) -> Hypothesis:
        h = Hypothesis(self._next_id, source, target, relation, value, confidence)
        self._next_id += 1
        self.hypotheses[h.hypothesis_id] = h
        return h

    def observe(self, target: Hashable, relation: Hashable, value: Hashable) -> None:
        self.time += 1
        self.facts.add((target, relation, value))
        eps = 1e-12
        for h in self.hypotheses.values():
            if h.target != target or h.relation != relation or h.status == "rejected":
                continue
            if h.value == value:
                h.confirmations += 1
                event = "confirm"
            else:
                h.rejections += 1
                event = "reject"
            p = h.posterior_confidence
            if p + eps >= self.support_threshold:
                h.status = "supported"
            elif p - eps <= self.reject_threshold:
                h.status = "rejected"
            else:
                h.status = "pending"
            h.history.append((self.time, event, p))

    def get(self, hypothesis_id: int) -> Hypothesis:
        return self.hypotheses[hypothesis_id]
