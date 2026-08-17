from __future__ import annotations

from dataclasses import dataclass, field
from typing import Hashable, Iterable


Node = Hashable


@dataclass(slots=True)
class KnowledgeNode:
    knowledge_id: str
    payload: object
    modalities: set[str] = field(default_factory=set)
    provenance: set[str] = field(default_factory=set)
    accesses: int = 0


class MultiTrajectoryMemory:
    """Experimental v0.87 memory: many trajectories resolve one knowledge node.

    Payload is stored once per knowledge_id. Arbitrarily many paths, agents and
    modalities can point to that node. This tests structural sharing; it does
    not yet claim semantic equivalence between independently learned payloads.
    """

    def __init__(self):
        self._knowledge: dict[str, KnowledgeNode] = {}
        self._routes: dict[tuple[Node, ...], str] = {}

    def store(
        self,
        knowledge_id: str,
        payload: object,
        trajectory: Iterable[Node],
        *,
        modality: str,
        provenance: str,
    ) -> None:
        route = tuple(trajectory)
        if not route:
            raise ValueError("trajectory must not be empty")
        existing = self._knowledge.get(knowledge_id)
        if existing is None:
            existing = KnowledgeNode(knowledge_id, payload)
            self._knowledge[knowledge_id] = existing
        elif existing.payload != payload:
            raise ValueError("same knowledge_id cannot silently overwrite payload")
        owner = self._routes.get(route)
        if owner is not None and owner != knowledge_id:
            raise ValueError("trajectory collision")
        self._routes[route] = knowledge_id
        existing.modalities.add(modality)
        existing.provenance.add(provenance)

    def resolve(self, trajectory: Iterable[Node]) -> KnowledgeNode | None:
        knowledge_id = self._routes.get(tuple(trajectory))
        if knowledge_id is None:
            return None
        node = self._knowledge[knowledge_id]
        node.accesses += 1
        return node

    @property
    def knowledge_count(self) -> int:
        return len(self._knowledge)

    @property
    def route_count(self) -> int:
        return len(self._routes)

    def duplication_ratio(self) -> float:
        """Payload copies avoided relative to naive one-payload-per-route storage."""
        if not self._routes:
            return 0.0
        return 1.0 - (len(self._knowledge) / len(self._routes))
