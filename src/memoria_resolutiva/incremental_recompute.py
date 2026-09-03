from __future__ import annotations

from dataclasses import dataclass, field
from collections import deque
from typing import Hashable, Callable, Mapping


CombineFn = Callable[[list[float]], float]


@dataclass(slots=True)
class ComputeNode:
    node_id: Hashable
    parents: tuple[Hashable, ...]
    value: float = 0.0
    history: list[float] = field(default_factory=list)
    combine: CombineFn | None = None


@dataclass(frozen=True, slots=True)
class RecomputeDecision:
    mode: str
    touched: tuple[Hashable, ...]
    affected_fraction: float


class IncrementalRecomputeGraph:
    """DAG recomputation with reverse dependency tracking.

    Root nodes may be updated directly. Derived nodes are recomputed only when
    reachable from changed roots. Each derived node may optionally provide its
    own combine rule; nodes without one inherit the graph default. A full
    recomputation method and an adaptive policy are provided for equivalence
    and density-aware execution.
    """

    def __init__(self, combine: CombineFn | None = None):
        self.nodes: dict[Hashable, ComputeNode] = {}
        self.children: dict[Hashable, set[Hashable]] = {}
        self.combine = combine or (lambda xs: sum(xs) / len(xs) if xs else 0.0)

    def add_root(self, node_id: Hashable, value: float) -> None:
        self.nodes[node_id] = ComputeNode(node_id, (), value, [value])
        self.children.setdefault(node_id, set())

    def _combine_node(self, node: ComputeNode) -> float:
        combine = node.combine or self.combine
        return combine([self.nodes[p].value for p in node.parents])

    def add_derived(
        self,
        node_id: Hashable,
        parents: list[Hashable],
        *,
        combine: CombineFn | None = None,
    ) -> None:
        if not parents:
            raise ValueError("derived node requires parents")
        if any(p not in self.nodes for p in parents):
            raise KeyError("all parents must exist")
        node = ComputeNode(node_id, tuple(parents), combine=combine)
        node.value = self._combine_node(node)
        node.history.append(node.value)
        self.nodes[node_id] = node
        self.children.setdefault(node_id, set())
        for p in parents:
            self.children.setdefault(p, set()).add(node_id)

    def _affected(self, changed: set[Hashable]) -> set[Hashable]:
        seen = set(changed)
        q = deque(changed)
        while q:
            cur = q.popleft()
            for child in self.children.get(cur, ()):
                if child not in seen:
                    seen.add(child)
                    q.append(child)
        return seen

    def _topological_subset(self, subset: set[Hashable]) -> list[Hashable]:
        indegree = {n: sum(1 for p in self.nodes[n].parents if p in subset) for n in subset}
        q = deque([n for n, d in indegree.items() if d == 0])
        order = []
        while q:
            n = q.popleft()
            order.append(n)
            for child in self.children.get(n, ()):
                if child in indegree:
                    indegree[child] -= 1
                    if indegree[child] == 0:
                        q.append(child)
        if len(order) != len(subset):
            raise ValueError("cycle detected")
        return order

    def _validate_root_updates(self, updates: Mapping[Hashable, float]) -> set[Hashable]:
        changed = set(updates)
        for node_id in changed:
            if node_id not in self.nodes:
                raise KeyError(node_id)
            if self.nodes[node_id].parents:
                raise ValueError("only root nodes can be updated directly")
        return changed

    def _apply_root_updates(self, updates: Mapping[Hashable, float]) -> None:
        for node_id, value in updates.items():
            node = self.nodes[node_id]
            node.value = value
            node.history.append(value)

    def update_roots_incremental(self, updates: Mapping[Hashable, float]) -> list[Hashable]:
        """Apply several root changes and recompute their affected union once."""
        if not updates:
            return []

        changed = self._validate_root_updates(updates)
        self._apply_root_updates(updates)

        affected = self._affected(changed)
        order = self._topological_subset(affected)
        touched = []
        for node_id in order:
            if node_id not in changed:
                current = self.nodes[node_id]
                current.value = self._combine_node(current)
                current.history.append(current.value)
            touched.append(node_id)
        return touched

    def update_roots_adaptive(
        self,
        updates: Mapping[Hashable, float],
        *,
        full_threshold: float = 0.5,
    ) -> RecomputeDecision:
        """Choose incremental or full recomputation from affected-graph density.

        `full_threshold` is the affected-node fraction at which a full
        recomputation is selected. The decision is deterministic and based on
        graph topology before values are changed. Both paths preserve the same
        final snapshot semantics.
        """
        if not 0.0 < full_threshold <= 1.0:
            raise ValueError("full_threshold must be in (0, 1]")
        if not updates:
            return RecomputeDecision("incremental", (), 0.0)

        changed = self._validate_root_updates(updates)
        affected = self._affected(changed)
        affected_fraction = len(affected) / len(self.nodes) if self.nodes else 0.0

        if affected_fraction < full_threshold:
            touched = self.update_roots_incremental(updates)
            return RecomputeDecision("incremental", tuple(touched), affected_fraction)

        self._apply_root_updates(updates)
        touched = self.full_recompute()
        return RecomputeDecision("full", tuple(touched), affected_fraction)

    def update_root_incremental(self, node_id: Hashable, value: float) -> list[Hashable]:
        return self.update_roots_incremental({node_id: value})

    def full_recompute(self) -> list[Hashable]:
        subset = set(self.nodes)
        order = self._topological_subset(subset)
        touched = []
        for n in order:
            current = self.nodes[n]
            if current.parents:
                current.value = self._combine_node(current)
                current.history.append(current.value)
            touched.append(n)
        return touched

    def snapshot(self) -> dict[Hashable, float]:
        return {k: v.value for k, v in self.nodes.items()}
