from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable


@dataclass(frozen=True, slots=True)
class TransferCandidate:
    source: Hashable
    target: Hashable
    relation: Hashable
    value: Hashable
    similarity: float
    support: int
    confidence: float
    status: str  # candidate | abstain


class AnalogicalTransfer:
    """Conservative transfer across convergent concepts.

    Relations are never copied as facts. They become candidates whose confidence
    depends on structural similarity and independent support. Conflicting target
    evidence forces abstention.
    """

    def __init__(self, min_similarity: float = 0.80, min_support: int = 2, accept_confidence: float = 0.70):
        self.min_similarity = min_similarity
        self.min_support = min_support
        self.accept_confidence = accept_confidence
        self._facts: dict[Hashable, dict[Hashable, set[Hashable]]] = {}

    def observe(self, concept: Hashable, relation: Hashable, value: Hashable) -> None:
        self._facts.setdefault(concept, {}).setdefault(relation, set()).add(value)

    def values(self, concept: Hashable, relation: Hashable) -> set[Hashable]:
        return set(self._facts.get(concept, {}).get(relation, set()))

    def propose(self, source: Hashable, target: Hashable, relation: Hashable, similarity: float, independent_support: int = 1) -> list[TransferCandidate]:
        if similarity < self.min_similarity:
            return []
        source_values = self.values(source, relation)
        if not source_values:
            return []
        target_values = self.values(target, relation)
        # Existing contradictory target knowledge blocks transfer.
        if target_values and not source_values.issubset(target_values):
            return [TransferCandidate(source, target, relation, v, similarity, independent_support, 0.0, "abstain") for v in source_values]
        confidence = similarity * min(1.0, independent_support / max(1, self.min_support))
        status = "candidate" if independent_support >= self.min_support and confidence >= self.accept_confidence else "abstain"
        return [TransferCandidate(source, target, relation, v, similarity, independent_support, confidence, status) for v in source_values]
