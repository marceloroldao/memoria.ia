from __future__ import annotations

from dataclasses import dataclass
from typing import Hashable, Iterable

from .multitrajectory import MultiTrajectoryMemory
from .saturating_lifecycle import SaturatingMemoryLifecycle


Node = Hashable


@dataclass(frozen=True, slots=True)
class RouteStatus:
    knowledge_id: str
    active_depth: int
    historical_depth: int


class RoutedLifecycleMemory:
    """Shared knowledge payloads with independent lifecycle per trajectory.

    A route may weaken, deactivate or reactivate without mutating the shared
    payload or the lifecycle state of other routes that resolve to the same
    knowledge node.
    """

    def __init__(self, levels: int = 5, max_strength: float = 1.25):
        self.knowledge = MultiTrajectoryMemory()
        self.levels = levels
        self.max_strength = max_strength
        self._route_lifecycle: dict[tuple[Node, ...], SaturatingMemoryLifecycle] = {}

    def register(self, knowledge_id: str, payload: object, trajectory: Iterable[Node], *, modality: str, provenance: str) -> None:
        route = tuple(trajectory)
        self.knowledge.store(
            knowledge_id, payload, route,
            modality=modality, provenance=provenance,
        )
        self._route_lifecycle.setdefault(
            route,
            SaturatingMemoryLifecycle(levels=self.levels, max_strength=self.max_strength),
        )

    def support(self, trajectory: Iterable[Node], amount: float = 1.0) -> None:
        route = tuple(trajectory)
        lifecycle = self._route_lifecycle[route]
        lifecycle.support("route", amount)

    def contradict(self, trajectory: Iterable[Node], amount: float = 1.0) -> None:
        route = tuple(trajectory)
        lifecycle = self._route_lifecycle[route]
        lifecycle.contradict("route", amount)

    def resolve(self, trajectory: Iterable[Node], require_active: bool = True):
        route = tuple(trajectory)
        lifecycle = self._route_lifecycle.get(route)
        if lifecycle is None:
            return None
        if require_active and lifecycle.active_depth("route") < 0:
            return None
        return self.knowledge.resolve(route)

    def status(self, trajectory: Iterable[Node]) -> RouteStatus | None:
        route = tuple(trajectory)
        node = self.knowledge.resolve(route)
        lifecycle = self._route_lifecycle.get(route)
        if node is None or lifecycle is None:
            return None
        return RouteStatus(
            knowledge_id=node.knowledge_id,
            active_depth=lifecycle.active_depth("route"),
            historical_depth=lifecycle.historical_depth("route"),
        )
