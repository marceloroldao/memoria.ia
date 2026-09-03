"""Measure batched incremental recomputation as correction bursts grow.

Uses the ~16k-node balanced hierarchy and compares batched incremental updates
against full recomputation for increasing numbers of changed roots.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass

from benchmarks.layered_scale import build_balanced_graph


@dataclass(frozen=True)
class BurstResult:
    changed_roots: int
    total_nodes: int
    batch_touched: int
    full_touched: int
    batch_ms: float
    full_ms: float
    snapshots_equal: bool


def _updates(count: int) -> dict[str, float]:
    return {f"r{i}": -float(i + 1) for i in range(count)}


def run_burst(changed_roots: int, target_nodes: int = 10_000) -> BurstResult:
    graph, _, _ = build_balanced_graph(target_nodes)
    total_nodes = len(graph.snapshot())
    updates = _updates(changed_roots)

    started = time.perf_counter()
    batch_touched = graph.update_roots_incremental(updates)
    batch_ms = (time.perf_counter() - started) * 1000.0
    batch_snapshot = graph.snapshot()

    full_graph, _, _ = build_balanced_graph(target_nodes)
    for node_id, value in updates.items():
        node = full_graph.nodes[node_id]
        node.value = value
        node.history.append(value)
    started = time.perf_counter()
    full_touched = full_graph.full_recompute()
    full_ms = (time.perf_counter() - started) * 1000.0
    full_snapshot = full_graph.snapshot()

    return BurstResult(
        changed_roots=changed_roots,
        total_nodes=total_nodes,
        batch_touched=len(batch_touched),
        full_touched=len(full_touched),
        batch_ms=batch_ms,
        full_ms=full_ms,
        snapshots_equal=batch_snapshot == full_snapshot,
    )


def run_suite() -> list[BurstResult]:
    return [run_burst(n) for n in (1, 2, 4, 8, 16, 32, 64, 128, 256, 512, 1024)]


if __name__ == "__main__":
    print(json.dumps([asdict(item) for item in run_suite()], indent=2, sort_keys=True))
