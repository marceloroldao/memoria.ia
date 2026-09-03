"""Resource benchmark for layered recomputation.

Measures graph build time, incremental correction latency, full recomputation
latency and Python heap peak via tracemalloc for ~100, ~1k and ~10k nodes.
No LLM, network or external service is involved.
"""
from __future__ import annotations

import json
import time
import tracemalloc
from dataclasses import asdict, dataclass

from benchmarks.layered_scale import build_balanced_graph


@dataclass(frozen=True)
class ResourceResult:
    target_nodes: int
    actual_nodes: int
    build_ms: float
    incremental_ms: float
    full_ms: float
    peak_heap_bytes: int
    incremental_touched: int
    full_touched: int
    snapshots_equal: bool


def run_resource(target_nodes: int) -> ResourceResult:
    tracemalloc.start()
    started = time.perf_counter()
    graph, changed_root, _depth = build_balanced_graph(target_nodes)
    build_ms = (time.perf_counter() - started) * 1000.0
    actual_nodes = len(graph.snapshot())
    _, peak_heap_bytes = tracemalloc.get_traced_memory()

    started = time.perf_counter()
    incremental_touched = graph.update_root_incremental(changed_root, -1.0)
    incremental_ms = (time.perf_counter() - started) * 1000.0
    incremental_snapshot = graph.snapshot()

    full_graph, _, _ = build_balanced_graph(target_nodes)
    root = full_graph.nodes[changed_root]
    root.value = -1.0
    root.history.append(-1.0)
    started = time.perf_counter()
    full_touched = full_graph.full_recompute()
    full_ms = (time.perf_counter() - started) * 1000.0
    full_snapshot = full_graph.snapshot()

    _current, peak2 = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_heap_bytes = max(peak_heap_bytes, peak2)

    return ResourceResult(
        target_nodes=target_nodes,
        actual_nodes=actual_nodes,
        build_ms=build_ms,
        incremental_ms=incremental_ms,
        full_ms=full_ms,
        peak_heap_bytes=peak_heap_bytes,
        incremental_touched=len(incremental_touched),
        full_touched=len(full_touched),
        snapshots_equal=incremental_snapshot == full_snapshot,
    )


def run_suite() -> list[ResourceResult]:
    return [run_resource(size) for size in (100, 1_000, 10_000)]


if __name__ == "__main__":
    print(json.dumps([asdict(item) for item in run_suite()], indent=2, sort_keys=True))
