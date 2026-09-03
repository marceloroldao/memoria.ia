"""Deterministic scale benchmark for layered incremental recomputation.

Builds balanced binary hierarchies with approximately 100, 1,000 and 10,000
nodes, changes one root, and compares incremental recomputation against a full
recompute. No LLM or network is involved.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from typing import Iterable

from memoria_resolutiva.incremental_recompute import IncrementalRecomputeGraph


@dataclass(frozen=True)
class ScaleResult:
    target_nodes: int
    actual_nodes: int
    depth: int
    incremental_touched: int
    full_touched: int
    touched_reduction_ratio: float
    incremental_ms: float
    full_ms: float
    snapshots_equal: bool


def _sum(values: Iterable[float]) -> float:
    return float(sum(values))


def build_balanced_graph(target_nodes: int) -> tuple[IncrementalRecomputeGraph, str, int]:
    if target_nodes < 3:
        raise ValueError("target_nodes must be >= 3")

    # For a full binary tree, total nodes = 2*leaves-1. Choose enough leaves to
    # meet/exceed the requested scale while keeping the graph deterministic.
    leaves = 1
    while 2 * leaves - 1 < target_nodes:
        leaves *= 2

    graph = IncrementalRecomputeGraph()
    current: list[str] = []
    for idx in range(leaves):
        node_id = f"r{idx}"
        graph.add_root(node_id, float(idx + 1))
        current.append(node_id)

    depth = 0
    while len(current) > 1:
        nxt: list[str] = []
        for idx in range(0, len(current), 2):
            node_id = f"l{depth + 1}_{idx // 2}"
            graph.add_derived(node_id, (current[idx], current[idx + 1]), _sum)
            nxt.append(node_id)
        current = nxt
        depth += 1

    return graph, "r0", depth


def run_scale(target_nodes: int) -> ScaleResult:
    graph, changed_root, depth = build_balanced_graph(target_nodes)
    actual_nodes = len(graph.snapshot())

    started = time.perf_counter()
    incremental_touched = graph.update_root_incremental(changed_root, -1.0)
    incremental_ms = (time.perf_counter() - started) * 1000.0
    incremental_snapshot = graph.snapshot()

    # Rebuild the same graph so the full path starts from the identical state.
    full_graph, _, _ = build_balanced_graph(target_nodes)
    full_graph.set_root(changed_root, -1.0)
    started = time.perf_counter()
    full_touched = full_graph.full_recompute()
    full_ms = (time.perf_counter() - started) * 1000.0
    full_snapshot = full_graph.snapshot()

    return ScaleResult(
        target_nodes=target_nodes,
        actual_nodes=actual_nodes,
        depth=depth,
        incremental_touched=len(incremental_touched),
        full_touched=len(full_touched),
        touched_reduction_ratio=1.0 - (len(incremental_touched) / len(full_touched)),
        incremental_ms=incremental_ms,
        full_ms=full_ms,
        snapshots_equal=incremental_snapshot == full_snapshot,
    )


def run_suite() -> list[ScaleResult]:
    return [run_scale(size) for size in (100, 1_000, 10_000)]


if __name__ == "__main__":
    print(json.dumps([asdict(item) for item in run_suite()], indent=2, sort_keys=True))
