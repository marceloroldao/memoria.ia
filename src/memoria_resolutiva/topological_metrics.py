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
