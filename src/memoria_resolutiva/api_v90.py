from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Iterable

from .distributed_consensus import KnowledgeDescriptor, compare_knowledge
from .routed_lifecycle import RoutedLifecycleMemory
from .routed_persistence import load_routed_snapshot, save_routed_snapshot

Node = Hashable


@dataclass(frozen=True, slots=True)
class MemoryConfig:
    levels: int = 5
    max_strength: float = 1.25


class ResolutiveMemoryAPI:
    """v0.95 stable public facade.

    The v0.95.0 contract freezes the validated public operations while internal
    implementations may continue to evolve compatibly toward the v1.0 gate.
    """

    API_VERSION = "0.95.0"

    def __init__(self, config: MemoryConfig | None = None):
        self.config = config or MemoryConfig()
        self._memory = RoutedLifecycleMemory(
            levels=self.config.levels,
            max_strength=self.config.max_strength,
        )

    def remember(self, knowledge_id: str, payload: object, trajectory: Iterable[Node], *, modality: str, provenance: str) -> None:
        self._memory.register(
            knowledge_id, payload, trajectory,
            modality=modality, provenance=provenance,
        )

    def reinforce(self, trajectory: Iterable[Node], amount: float = 1.0) -> None:
        self._memory.support(trajectory, amount)

    def challenge(self, trajectory: Iterable[Node], amount: float = 1.0) -> None:
        self._memory.contradict(trajectory, amount)

    def recall(self, trajectory: Iterable[Node], *, include_inactive: bool = False):
        return self._memory.resolve(trajectory, require_active=not include_inactive)

    def route_status(self, trajectory: Iterable[Node]):
        return self._memory.status(trajectory)

    def save(self, path) -> None:
        save_routed_snapshot(self._memory, path)

    @classmethod
    def load(cls, path):
        routed = load_routed_snapshot(path)
        obj = cls(MemoryConfig(levels=routed.levels, max_strength=routed.max_strength))
        obj._memory = routed
        return obj

    @staticmethod
    def compare(a: KnowledgeDescriptor, b: KnowledgeDescriptor):
        return compare_knowledge(a, b)
