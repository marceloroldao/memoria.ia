from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from math import exp

from .textual import TextContextMemory, tokenize


@dataclass(frozen=True, slots=True)
class TemporalAssociation:
    candidate: str
    score: float


@dataclass(frozen=True, slots=True)
class TemporalChange:
    epoch: int
    label: str
    previous: str | None
    current: str | None
    previous_score: float
    current_score: float


class TemporalContextMemory:
    """Temporal semantic/context similarity memory.

    This class answers which tokens occur in similar signed neighborhoods. It must
    not be confused with direct episodic relation memory such as `rota -> ponte`.
    """

    def __init__(self, radius: int = 3, decay: float = 0.8):
        if not 0.0 < decay <= 1.0:
            raise ValueError("decay must be in (0, 1]")
        self.radius = radius
        self.decay = decay
        self.epochs: list[TextContextMemory] = []
        self.epoch_labels: list[str] = []

    def add_epoch(self, sentences, label: str | None = None) -> int:
        memory = TextContextMemory(radius=self.radius)
        memory.observe_many(sentences)
        self.epochs.append(memory)
        self.epoch_labels.append(label or f"epoch-{len(self.epochs) - 1}")
        return len(self.epochs) - 1

    def similarity_at(self, epoch: int, a: str, b: str) -> float:
        return self.epochs[epoch].associator.similarity(a.lower(), b.lower())

    def current_similarity(self, a: str, b: str) -> float:
        if not self.epochs:
            return 0.0
        latest = len(self.epochs) - 1
        weighted = 0.0
        total_weight = 0.0
        for idx, memory in enumerate(self.epochs):
            age = latest - idx
            weight = exp(-self.decay * age)
            total_weight += weight
            weighted += weight * memory.associator.similarity(a.lower(), b.lower())
        return weighted / total_weight if total_weight else 0.0

    def nearest_current(self, token: str, top_k: int = 5) -> list[TemporalAssociation]:
        token = token.lower()
        candidates: set[str] = set()
        for epoch in self.epochs:
            candidates.update(epoch.associator.profiles)
        candidates.discard(token)
        ranked = [TemporalAssociation(c, self.current_similarity(token, c)) for c in candidates]
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:top_k]

    def nearest_at(self, epoch: int, token: str, top_k: int = 5) -> list[TemporalAssociation]:
        ranked = self.epochs[epoch].nearest(token, top_k=top_k)
        return [TemporalAssociation(candidate, score) for candidate, score in ranked]

    def change_score(self, token: str, old_partner: str, new_partner: str) -> float:
        return self.current_similarity(token, new_partner) - self.current_similarity(token, old_partner)


class TemporalRelationMemory:
    """Episodic memory for direct local token relations across temporal epochs.

    Each epoch stores sparse co-occurrence edges. An edge receives inverse-distance
    evidence when two tokens occur within `radius` positions in an observation.
    Historical edges are never deleted. Current queries use exponential recency
    weighting across all epochs, while historical queries inspect one epoch only.
    """

    def __init__(self, radius: int = 3, decay: float = 0.8):
        if radius < 1:
            raise ValueError("radius must be >= 1")
        if not 0.0 < decay <= 1.0:
            raise ValueError("decay must be in (0, 1]")
        self.radius = radius
        self.decay = decay
        self.epochs: list[dict[str, Counter[str]]] = []
        self.epoch_labels: list[str] = []

    def _build_epoch(self, sentences) -> dict[str, Counter[str]]:
        edges: dict[str, Counter[str]] = defaultdict(Counter)
        for sentence in sentences:
            tokens = tokenize(sentence)
            for i, token in enumerate(tokens):
                lo = max(0, i - self.radius)
                hi = min(len(tokens), i + self.radius + 1)
                for j in range(lo, hi):
                    if i == j:
                        continue
                    distance = abs(j - i)
                    edges[token][tokens[j]] += 1.0 / distance
        return dict(edges)

    def add_epoch(self, sentences, label: str | None = None) -> int:
        self.epochs.append(self._build_epoch(sentences))
        self.epoch_labels.append(label or f"epoch-{len(self.epochs) - 1}")
        return len(self.epochs) - 1

    def relation_at(self, epoch: int, source: str, target: str) -> float:
        return float(self.epochs[epoch].get(source.lower(), Counter()).get(target.lower(), 0.0))

    def current_relation(self, source: str, target: str) -> float:
        if not self.epochs:
            return 0.0
        latest = len(self.epochs) - 1
        weighted = 0.0
        total_weight = 0.0
        for idx in range(len(self.epochs)):
            weight = exp(-self.decay * (latest - idx))
            weighted += weight * self.relation_at(idx, source, target)
            total_weight += weight
        return weighted / total_weight if total_weight else 0.0

    def dominant_at(self, epoch: int, source: str, candidates: list[str] | tuple[str, ...] | None = None) -> TemporalAssociation | None:
        source = source.lower()
        outgoing = self.epochs[epoch].get(source)
        if not outgoing:
            return None
        allowed = set(c.lower() for c in candidates) if candidates else None
        items = [(target, float(score)) for target, score in outgoing.items() if allowed is None or target in allowed]
        if not items:
            return None
        target, score = max(items, key=lambda item: item[1])
        return TemporalAssociation(target, score)

    def dominant_current(self, source: str, candidates: list[str] | tuple[str, ...] | None = None) -> TemporalAssociation | None:
        source = source.lower()
        universe: set[str] = set()
        for epoch in self.epochs:
            universe.update(epoch.get(source, Counter()))
        if candidates:
            universe &= {c.lower() for c in candidates}
        if not universe:
            return None
        ranked = [(target, self.current_relation(source, target)) for target in universe]
        target, score = max(ranked, key=lambda item: item[1])
        return TemporalAssociation(target, score)

    def timeline(self, source: str, candidates: list[str] | tuple[str, ...] | None = None) -> list[TemporalAssociation | None]:
        return [self.dominant_at(epoch, source, candidates) for epoch in range(len(self.epochs))]

    def detect_changes(self, source: str, candidates: list[str] | tuple[str, ...] | None = None) -> list[TemporalChange]:
        changes: list[TemporalChange] = []
        previous: TemporalAssociation | None = None
        for epoch, current in enumerate(self.timeline(source, candidates)):
            previous_name = previous.candidate if previous else None
            current_name = current.candidate if current else None
            if epoch == 0 or current_name != previous_name:
                changes.append(
                    TemporalChange(
                        epoch=epoch,
                        label=self.epoch_labels[epoch],
                        previous=previous_name,
                        current=current_name,
                        previous_score=previous.score if previous else 0.0,
                        current_score=current.score if current else 0.0,
                    )
                )
            previous = current
        return changes
