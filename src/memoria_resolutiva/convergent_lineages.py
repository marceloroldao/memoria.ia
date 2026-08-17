from __future__ import annotations

from dataclasses import dataclass
import math


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@dataclass(frozen=True, slots=True)
class LineageProfile:
    lineage: str
    parent: str | None
    vector: tuple[float, ...]


@dataclass(frozen=True, slots=True)
class ConvergenceDecision:
    kind: str  # independent | convergent | ambiguous
    left: str
    right: str
    similarity: float
    macro_concept: str | None


class ConvergentLineageMemory:
    """Detect convergence without erasing independent ancestry.

    A macro-concept is a derived grouping above the lineages. It never rewrites
    parent links or replaces the original profiles.
    """

    def __init__(self, convergence_threshold: float = 0.90, ambiguity_band: float = 0.03):
        self.convergence_threshold = convergence_threshold
        self.ambiguity_band = ambiguity_band
        self.lineages: dict[str, LineageProfile] = {}
        self.macro_members: dict[str, tuple[str, str]] = {}

    def remember(self, lineage: str, vector: list[float], parent: str | None = None) -> None:
        self.lineages[lineage] = LineageProfile(lineage, parent, tuple(vector))

    def ancestry(self, lineage: str) -> list[str]:
        path: list[str] = []
        current = self.lineages.get(lineage)
        seen: set[str] = set()
        while current is not None and current.lineage not in seen:
            path.append(current.lineage)
            seen.add(current.lineage)
            current = self.lineages.get(current.parent) if current.parent else None
        return path

    def compare(self, left: str, right: str) -> ConvergenceDecision:
        a = self.lineages[left]
        b = self.lineages[right]
        sim = cosine(list(a.vector), list(b.vector))
        if abs(sim - self.convergence_threshold) <= self.ambiguity_band:
            return ConvergenceDecision("ambiguous", left, right, sim, None)
        if sim < self.convergence_threshold:
            return ConvergenceDecision("independent", left, right, sim, None)
        macro = f"macro:{'|'.join(sorted((left, right)))}"
        self.macro_members[macro] = tuple(sorted((left, right)))
        return ConvergenceDecision("convergent", left, right, sim, macro)

    def members(self, macro_concept: str) -> tuple[str, str]:
        return self.macro_members[macro_concept]
