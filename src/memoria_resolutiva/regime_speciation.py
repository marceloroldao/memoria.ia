from __future__ import annotations

from dataclasses import dataclass, field

from .partial_recurrence import cosine


@dataclass(slots=True)
class RegimeNode:
    name: str
    profile: list[float]
    parent: str | None = None
    generation: int = 0


@dataclass(frozen=True, slots=True)
class SpeciationEvent:
    source: str
    child: str
    similarity_to_parent: float
    generation: int


class RegimeLineageMemory:
    """Track variants and promote persistent divergence into new regime identity."""

    def __init__(self, variant_threshold: float = 0.78, speciation_threshold: float = 0.70, persistence: int = 3):
        if not 0 <= speciation_threshold <= variant_threshold <= 1:
            raise ValueError("invalid thresholds")
        if persistence <= 0:
            raise ValueError("persistence must be positive")
        self.variant_threshold = variant_threshold
        self.speciation_threshold = speciation_threshold
        self.persistence = persistence
        self.nodes: dict[str, RegimeNode] = {}
        self._drift_counts: dict[str, int] = {}
        self.events: list[SpeciationEvent] = []

    def remember_root(self, name: str, profile: list[float]) -> None:
        self.nodes[name] = RegimeNode(name, list(profile), None, 0)

    def observe_variant(self, parent: str, profile: list[float], child_name: str) -> str:
        if parent not in self.nodes:
            raise KeyError(parent)
        sim = cosine(profile, self.nodes[parent].profile)
        if sim >= self.variant_threshold:
            self._drift_counts[parent] = 0
            return "variant"
        if sim <= self.speciation_threshold:
            self._drift_counts[parent] = self._drift_counts.get(parent, 0) + 1
        else:
            self._drift_counts[parent] = max(0, self._drift_counts.get(parent, 0) - 1)
        if self._drift_counts[parent] >= self.persistence:
            generation = self.nodes[parent].generation + 1
            self.nodes[child_name] = RegimeNode(child_name, list(profile), parent, generation)
            self.events.append(SpeciationEvent(parent, child_name, sim, generation))
            self._drift_counts[parent] = 0
            return "speciated"
        return "drifting"

    def lineage(self, name: str) -> list[str]:
        if name not in self.nodes:
            return []
        path = []
        current = self.nodes[name]
        while current is not None:
            path.append(current.name)
            current = self.nodes.get(current.parent) if current.parent else None
        return list(reversed(path))
