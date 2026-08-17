from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceItem:
    claim_id: str
    value: str
    source: str
    origin: str
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class EvidenceDecision:
    winner: str | None
    conflict: bool
    support: dict[str, float]
    independent_origins: dict[str, int]


class IndependentEvidenceResolver:
    """Resolve claims by independent origin, not raw source count.

    Sources sharing the same `origin` are treated as one evidence family for a
    claim. This prevents copied/repeated reports from creating artificial voting
    power. Within one origin family, only the strongest weight for each value is
    counted.
    """

    def __init__(self, min_margin: float = 0.15):
        if not 0.0 <= min_margin <= 1.0:
            raise ValueError("min_margin must be in [0, 1]")
        self.min_margin = min_margin
        self.items: list[EvidenceItem] = []

    def observe(self, item: EvidenceItem) -> None:
        if item.weight <= 0:
            raise ValueError("weight must be positive")
        self.items.append(item)

    def resolve(self, claim_id: str) -> EvidenceDecision:
        relevant = [item for item in self.items if item.claim_id == claim_id]
        if not relevant:
            return EvidenceDecision(None, True, {}, {})

        grouped: dict[str, dict[str, float]] = defaultdict(dict)
        for item in relevant:
            prev = grouped[item.origin].get(item.value, 0.0)
            grouped[item.origin][item.value] = max(prev, item.weight)

        support: dict[str, float] = defaultdict(float)
        origins: dict[str, set[str]] = defaultdict(set)
        for origin, values in grouped.items():
            # If one origin contradicts itself, its support is split by value; it
            # still counts as only one independent origin per value.
            for value, weight in values.items():
                support[value] += weight
                origins[value].add(origin)

        ranked = sorted(support.items(), key=lambda item: item[1], reverse=True)
        if len(ranked) == 1:
            value, _ = ranked[0]
            return EvidenceDecision(value, False, dict(support), {k: len(v) for k, v in origins.items()})

        top_value, top_score = ranked[0]
        second_score = ranked[1][1]
        total = sum(support.values())
        margin = (top_score - second_score) / total if total else 0.0
        conflict = margin < self.min_margin
        return EvidenceDecision(
            None if conflict else top_value,
            conflict,
            dict(support),
            {k: len(v) for k, v in origins.items()},
        )
