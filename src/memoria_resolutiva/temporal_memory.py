from __future__ import annotations

from dataclasses import dataclass
from math import exp

from .textual import TextContextMemory


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
    """Online contextual memory with explicit temporal epochs.

    Observations are never deleted from historical epochs. Current queries combine
    epoch-local similarities with exponentially decaying recency weights, while
    historical queries can inspect any epoch directly.
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
            score = memory.associator.similarity(a.lower(), b.lower())
            weighted += weight * score
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

    def dominant_at(self, epoch: int, token: str) -> TemporalAssociation | None:
        ranked = self.nearest_at(epoch, token, top_k=1)
        return ranked[0] if ranked else None

    def dominant_current(self, token: str) -> TemporalAssociation | None:
        ranked = self.nearest_current(token, top_k=1)
        return ranked[0] if ranked else None

    def timeline(self, token: str) -> list[TemporalAssociation | None]:
        """Return the dominant association independently for every historical epoch."""
        return [self.dominant_at(epoch, token) for epoch in range(len(self.epochs))]

    def detect_changes(self, token: str) -> list[TemporalChange]:
        """Detect epochs where the dominant historical partner changes.

        This is intentionally epoch-local: it reports what each stored episode says,
        not the recency-weighted current belief.
        """
        changes: list[TemporalChange] = []
        previous: TemporalAssociation | None = None
        for epoch, current in enumerate(self.timeline(token)):
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

    def change_score(self, token: str, old_partner: str, new_partner: str) -> float:
        """Positive values indicate that recency-weighted evidence favors new_partner."""
        return self.current_similarity(token, new_partner) - self.current_similarity(token, old_partner)
