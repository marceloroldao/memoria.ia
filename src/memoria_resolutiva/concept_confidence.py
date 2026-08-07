from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ConfidenceEvent:
    epoch: int
    support_merge: float
    support_split: float
    confidence_merge: float


@dataclass(slots=True)
class ConceptConfidence:
    """Online confidence for merge-vs-split hypotheses.

    Confidence is maintained with a Beta-style posterior so one observation
    cannot force certainty. History is append-only and queryable by epoch.
    """

    prior_merge: float = 1.0
    prior_split: float = 1.0
    merge_support: float = 0.0
    split_support: float = 0.0
    history: list[ConfidenceEvent] = field(default_factory=list)

    def confidence_merge(self) -> float:
        a = self.prior_merge + self.merge_support
        b = self.prior_split + self.split_support
        return a / (a + b)

    def observe(self, epoch: int, *, merge_evidence: float = 0.0, split_evidence: float = 0.0) -> ConfidenceEvent:
        if merge_evidence < 0 or split_evidence < 0:
            raise ValueError("evidence must be non-negative")
        self.merge_support += merge_evidence
        self.split_support += split_evidence
        event = ConfidenceEvent(epoch, merge_evidence, split_evidence, self.confidence_merge())
        self.history.append(event)
        self.history.sort(key=lambda e: e.epoch)
        return event

    def at(self, epoch: int) -> float | None:
        candidates = [e for e in self.history if e.epoch <= epoch]
        return candidates[-1].confidence_merge if candidates else None

    def state(self, *, merge_threshold: float = 0.67, split_threshold: float = 0.33) -> str:
        c = self.confidence_merge()
        if c >= merge_threshold:
            return "merge"
        if c <= split_threshold:
            return "split"
        return "uncertain"
