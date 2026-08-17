from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .factual_timeline import FactEvent


@dataclass(frozen=True, slots=True)
class Evidence:
    event: FactEvent
    weight: float


@dataclass(frozen=True, slots=True)
class ConflictState:
    subject: str
    relation: str
    epoch: int
    scores: tuple[tuple[str, float], ...]
    conflict: bool
    winner: str | None
    confidence: float
    sources: tuple[tuple[str, str | None, float], ...]


class ProvenanceConflictMemory:
    """Temporal fact memory that preserves conflicting evidence and provenance.

    Facts are append-only. Resolution is evidence-weighted and intentionally
    abstains when the leading value is not sufficiently separated from rivals.
    """

    def __init__(self, decision_margin: float = 0.20):
        if not 0.0 <= decision_margin <= 1.0:
            raise ValueError("decision_margin must be in [0, 1]")
        self.decision_margin = decision_margin
        self._evidence: list[Evidence] = []

    def observe(
        self,
        epoch: int,
        subject: str,
        relation: str,
        value: str,
        *,
        source: str | None = None,
        weight: float = 1.0,
    ) -> Evidence:
        if weight <= 0:
            raise ValueError("weight must be > 0")
        evidence = Evidence(FactEvent(epoch, subject, relation, value, source), float(weight))
        self._evidence.append(evidence)
        self._evidence.sort(key=lambda item: item.event.epoch)
        return evidence

    def evidence_at(self, subject: str, relation: str, epoch: int) -> list[Evidence]:
        return [
            item for item in self._evidence
            if item.event.subject == subject
            and item.event.relation == relation
            and item.event.epoch <= epoch
        ]

    def resolve_at(self, subject: str, relation: str, epoch: int) -> ConflictState:
        evidence = self.evidence_at(subject, relation, epoch)
        if not evidence:
            return ConflictState(subject, relation, epoch, (), False, None, 0.0, ())

        latest_epoch = max(item.event.epoch for item in evidence)
        active = [item for item in evidence if item.event.epoch == latest_epoch]

        scores: dict[str, float] = defaultdict(float)
        sources: list[tuple[str, str | None, float]] = []
        for item in active:
            scores[item.event.value] += item.weight
            sources.append((item.event.value, item.event.source, item.weight))

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        total = sum(score for _, score in ranked)
        if total <= 0:
            return ConflictState(subject, relation, latest_epoch, tuple(ranked), True, None, 0.0, tuple(sources))

        top_value, top_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = (top_score - second_score) / total
        conflict = len(ranked) > 1 and margin < self.decision_margin
        winner = None if conflict else top_value
        confidence = top_score / total

        return ConflictState(
            subject,
            relation,
            latest_epoch,
            tuple(ranked),
            conflict,
            winner,
            confidence,
            tuple(sources),
        )

    def current(self, subject: str, relation: str) -> ConflictState:
        epochs = [
            item.event.epoch for item in self._evidence
            if item.event.subject == subject and item.event.relation == relation
        ]
        return self.resolve_at(subject, relation, max(epochs)) if epochs else ConflictState(subject, relation, -1, (), False, None, 0.0, ())
