from __future__ import annotations

from dataclasses import dataclass

from .topological_memory import AddressSpace, TopologicalNode


@dataclass(frozen=True, slots=True)
class NodeTopologyProfile:
    address: str
    kind: str
    canonical_value: str
    occurrences: int
    inbound_degree: int
    outbound_degree: int
    total_degree: int
    phrase_parent_count: int
    distinct_parent_kinds: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IngestionGrowthProfile:
    ingestions: int
    total_new_nodes: int
    total_reused_nodes: int
    average_new_nodes_per_ingestion: float
    average_reused_nodes_per_ingestion: float


@dataclass(frozen=True, slots=True)
class ActivationProfile:
    start_address: str
    direction: str
    max_depth: int
    max_candidates: int
    candidate_count: int
    truncated: bool
    candidates_by_kind: tuple[tuple[str, int], ...]


def profile_node(addresses: AddressSpace, node: TopologicalNode) -> NodeTopologyProfile:
    parent_kinds = []
    phrase_parent_count = 0
    for parent_address in node.edges_in:
        parent = addresses.node(parent_address)
        if parent is None:
            continue
        parent_kinds.append(parent.kind)
        if parent.kind == "phrase":
            phrase_parent_count += 1
    return NodeTopologyProfile(
        address=node.address,
        kind=node.kind,
        canonical_value=node.canonical_value,
        occurrences=node.occurrences,
        inbound_degree=len(node.edges_in),
        outbound_degree=len(node.edges_out),
        total_degree=node.density,
        phrase_parent_count=phrase_parent_count,
        distinct_parent_kinds=tuple(sorted(set(parent_kinds))),
    )


def profile_word(addresses: AddressSpace, word: str) -> NodeTopologyProfile | None:
    node = addresses.resolve("word", word)
    return None if node is None else profile_node(addresses, node)


def growth_profile(new_nodes: list[int], reused_nodes: list[int]) -> IngestionGrowthProfile:
    if len(new_nodes) != len(reused_nodes):
        raise ValueError("new_nodes and reused_nodes must have the same length")
    ingestions = len(new_nodes)
    total_new = sum(new_nodes)
    total_reused = sum(reused_nodes)
    return IngestionGrowthProfile(
        ingestions=ingestions,
        total_new_nodes=total_new,
        total_reused_nodes=total_reused,
        average_new_nodes_per_ingestion=0.0 if ingestions == 0 else total_new / ingestions,
        average_reused_nodes_per_ingestion=0.0 if ingestions == 0 else total_reused / ingestions,
    )


def measure_activation(
    addresses: AddressSpace,
    start: TopologicalNode,
    *,
    max_depth: int = 2,
    max_candidates: int = 256,
    direction: str = "in",
) -> ActivationProfile:
    """Measure bounded graph expansion without assigning relevance weights.

    This is benchmark instrumentation, not the production recall policy. The hard
    candidate cap lets experiments observe hub pressure without allowing an
    unbounded traversal to distort the test environment.
    """
    if max_depth < 0:
        raise ValueError("max_depth must be >= 0")
    if max_candidates < 1:
        raise ValueError("max_candidates must be >= 1")
    if direction not in {"in", "out", "both"}:
        raise ValueError("direction must be 'in', 'out', or 'both'")

    visited = {start.address}
    frontier = [start.address]
    by_kind: dict[str, int] = {}
    truncated = False

    for _depth in range(max_depth):
        next_frontier: list[str] = []
        for current_address in frontier:
            current = addresses.node(current_address)
            if current is None:
                continue
            neighbors: set[str] = set()
            if direction in {"in", "both"}:
                neighbors.update(current.edges_in)
            if direction in {"out", "both"}:
                neighbors.update(current.edges_out)
            for neighbor_address in sorted(neighbors):
                if neighbor_address in visited:
                    continue
                if len(visited) - 1 >= max_candidates:
                    truncated = True
                    break
                neighbor = addresses.node(neighbor_address)
                if neighbor is None:
                    continue
                visited.add(neighbor_address)
                next_frontier.append(neighbor_address)
                by_kind[neighbor.kind] = by_kind.get(neighbor.kind, 0) + 1
            if truncated:
                break
        if truncated or not next_frontier:
            break
        frontier = next_frontier

    return ActivationProfile(
        start_address=start.address,
        direction=direction,
        max_depth=max_depth,
        max_candidates=max_candidates,
        candidate_count=len(visited) - 1,
        truncated=truncated,
        candidates_by_kind=tuple(sorted(by_kind.items())),
    )
