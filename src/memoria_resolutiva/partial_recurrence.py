from __future__ import annotations

from dataclasses import dataclass
import math


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@dataclass(frozen=True, slots=True)
class RecurrenceDecision:
    kind: str  # recurrence | variant | novel | ambiguous
    regime: str | None
    similarity: float
    margin: float


class PartialRecurrenceClassifier:
    """Separate exact-ish recurrence, variants and novelty from stored profiles."""

    def __init__(self, recurrence_threshold: float = 0.96, variant_threshold: float = 0.78, ambiguity_margin: float = 0.04):
        if not 0 <= variant_threshold <= recurrence_threshold <= 1:
            raise ValueError("invalid thresholds")
        self.recurrence_threshold = recurrence_threshold
        self.variant_threshold = variant_threshold
        self.ambiguity_margin = ambiguity_margin
        self.profiles: dict[str, list[float]] = {}

    def remember(self, name: str, profile: list[float]) -> None:
        self.profiles[name] = list(profile)

    def classify(self, observed: list[float]) -> RecurrenceDecision:
        if not self.profiles:
            return RecurrenceDecision("novel", None, 0.0, 0.0)
        ranked = sorted(((cosine(observed, p), name) for name, p in self.profiles.items()), reverse=True)
        best, name = ranked[0]
        second = ranked[1][0] if len(ranked) > 1 else 0.0
        margin = best - second
        if best < self.variant_threshold:
            return RecurrenceDecision("novel", None, best, margin)
        if margin < self.ambiguity_margin:
            return RecurrenceDecision("ambiguous", None, best, margin)
        if best >= self.recurrence_threshold:
            return RecurrenceDecision("recurrence", name, best, margin)
        return RecurrenceDecision("variant", name, best, margin)
