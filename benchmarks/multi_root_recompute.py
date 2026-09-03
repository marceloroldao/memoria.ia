"""Benchmark batched incremental recomputation for multiple changed roots."""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

from benchmarks.layered_scale import build_balanced_graph


@dataclass(frozen=True)
class MultiRootResult:
    target_nodes: int
    actual_nodes: int
    changed_roots: int
    batched_touched: int
    sequential_touched_total: int
    full_touched: int
    batched_ms: float
    sequential_ms: float
    full_ms: float
    snapshots_equal: bool


def _updates_for(target_nodes: int, count: int) -> dict[str, float]:
    graph, _, _ = build_balanced_graph(target_nodes)
    roots = [key for key, node in graph.nodes.items() if not node.parents]
    if count > len(roots):
        raise ValueError("too many roots requested")
    step = max(1, len(roots) // count)
    chosen = [roots[min(i * step, len(roots) - 1)] for i in range(count)]
    return {node_id: -float(i + 1) for i, node_id in enumerate(chosen)}


def run_multi_root(target_nodes: int = 10_000, changed_roots: int = 8) -> MultiRootResult:
    updates = _updates_for(target_nodes, changed_roots)

    batched, _, _ = build_balanced_graph(target_nodes)
    started = time.perf_counter()
    batched_touched = batched.update_roots_incremental(updates)
    batched_ms = (time.perf_counter() - started) * 1000.0
    batched_snapshot = batched.snapshot()

    sequential, _, _ = build_balanced_graph(target_nodes)
    sequential_total = 0
    started = time.perf_counter()
    for node_id, value in updates.items():
        sequential_total += len(sequential.update_root_incremental(node_id, value))
    sequential_ms = (time.perf_counter() - started) * 1000.0
    sequential_snapshot = sequential.snapshot()

    full, _, _ = build_balanced_graph(target_nodes)
    for node_id, value in updates.items():
        node = full.nodes[node_id]
        node.value = value
        node.history.append(value)
    started = time.perf_counter()
    full_touched = full.full_recompute()
    full_ms = (time.perf_counter() - started) * 1000.0
    full_snapshot = full.snapshot()

    return MultiRootResult(
        target_nodes=target_nodes,
        actual_nodes=len(full.nodes),
        changed_roots=changed_roots,
        batched_touched=len(batched_touched),
        sequential_touched_total=sequential_total,
        full_touched=len(full_touched),
        batched_ms=batched_ms,
        sequential_ms=sequential_ms,
        full_ms=full_ms,
        snapshots_equal=(batched_snapshot == sequential_snapshot == full_snapshot),
    )


if __name__ == "__main__":
    print(json.dumps(asdict(run_multi_root()), indent=2, sort_keys=True))
