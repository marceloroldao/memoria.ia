from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Hashable


@dataclass(slots=True)
class BeliefNode:
    node_id: Hashable
    value: object
    active: bool = True
    version: int = 0
    history: list[tuple[int, object, bool]] = field(default_factory=list)


class CorrectionGraph:
    """Incremental reverse-dependency graph for localized belief revision.

    Root observations and derived beliefs are separate nodes. Corrections create
    a new version/history entry and only descendants reachable through reverse
    dependency edges are marked for reevaluation.
    """

    def __init__(self):
        self.nodes: dict[Hashable, BeliefNode] = {}
        self.parents: dict[Hashable, set[Hashable]] = defaultdict(set)
        self.children: dict[Hashable, set[Hashable]] = defaultdict(set)
        self.time = 0

    def add_node(self, node_id: Hashable, value: object, parents: set[Hashable] | None = None) -> None:
        if node_id in self.nodes:
            raise ValueError("node already exists")
        self.nodes[node_id] = BeliefNode(node_id, value)
        for parent in parents or set():
            if parent not in self.nodes:
                raise KeyError(f"unknown parent: {parent}")
            self.parents[node_id].add(parent)
            self.children[parent].add(node_id)

    def affected_descendants(self, node_id: Hashable) -> list[Hashable]:
        if node_id not in self.nodes:
            raise KeyError(node_id)
        seen: set[Hashable] = set()
        q = deque(self.children.get(node_id, set()))
        order: list[Hashable] = []
        while q:
            current = q.popleft()
            if current in seen:
                continue
            seen.add(current)
            order.append(current)
            q.extend(self.children.get(current, set()))
        return order

    def correct(self, node_id: Hashable, new_value: object, active: bool = True) -> list[Hashable]:
        node = self.nodes[node_id]
        self.time += 1
        node.history.append((self.time, node.value, node.active))
        node.value = new_value
        node.active = active
        node.version += 1
        return self.affected_descendants(node_id)

    def invalidate(self, node_id: Hashable) -> list[Hashable]:
        return self.correct(node_id, self.nodes[node_id].value, active=False)

    def lineage(self, node_id: Hashable) -> set[Hashable]:
        result: set[Hashable] = set()
        q = deque(self.parents.get(node_id, set()))
        while q:
            current = q.popleft()
            if current in result:
                continue
            result.add(current)
            q.extend(self.parents.get(current, set()))
        return result
