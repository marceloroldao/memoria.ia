from __future__ import annotations

from dataclasses import dataclass

from memoria_resolutiva.incremental_recompute import IncrementalRecomputeGraph


@dataclass(frozen=True, slots=True)
class DeepPartialRecomputeResult:
    total_nodes: int
    incremental_touched: int
    full_touched: int
    touched_reduction: float
    snapshots_equal: bool
    incremental_path: tuple[str, ...]


def _build_graph() -> IncrementalRecomputeGraph:
    graph = IncrementalRecomputeGraph()
    for idx in range(1, 9):
        graph.add_root(f"r{idx}", float(idx))

    graph.add_derived("a1", ["r1", "r2"])
    graph.add_derived("a2", ["r3", "r4"])
    graph.add_derived("a3", ["r5", "r6"])
    graph.add_derived("a4", ["r7", "r8"])
    graph.add_derived("b1", ["a1", "a2"])
    graph.add_derived("b2", ["a3", "a4"])
    graph.add_derived("top", ["b1", "b2"])
    return graph


def run_deep_partial_recompute() -> DeepPartialRecomputeResult:
    incremental = _build_graph()
    reference = _build_graph()

    incremental_touched_nodes = incremental.update_root_incremental("r1", 100.0)

    reference.update_root_incremental("r1", 100.0)
    full_touched_nodes = reference.full_recompute()

    total_nodes = len(incremental.nodes)
    reduction = 1.0 - (len(incremental_touched_nodes) / len(full_touched_nodes))

    return DeepPartialRecomputeResult(
        total_nodes=total_nodes,
        incremental_touched=len(incremental_touched_nodes),
        full_touched=len(full_touched_nodes),
        touched_reduction=reduction,
        snapshots_equal=incremental.snapshot() == reference.snapshot(),
        incremental_path=tuple(str(node) for node in incremental_touched_nodes),
    )
