from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter
from typing import Callable


@dataclass(frozen=True, slots=True)
class ScaleResult:
    total_nodes: int
    affected_nodes: int
    affected_fraction: float
    incremental_seconds: float
    full_seconds: float
    speedup: float
    touched_ratio: float


def build_chain_forest(total_nodes: int, branch_size: int) -> tuple[dict[int, list[int]], list[int]]:
    if total_nodes <= 0 or branch_size <= 0:
        raise ValueError("sizes must be positive")
    children = {i: [] for i in range(total_nodes)}
    roots = []
    for start in range(0, total_nodes, branch_size):
        roots.append(start)
        end = min(total_nodes, start + branch_size)
        for i in range(start, end - 1):
            children[i].append(i + 1)
    return children, roots


def descendants(children: dict[int, list[int]], root: int) -> list[int]:
    out = []
    stack = [root]
    seen = set()
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        out.append(node)
        stack.extend(children.get(node, ()))
    return out


def _work(node: int, state: list[float]) -> None:
    # Stable CPU-only synthetic recomputation cost.
    x = state[node]
    for _ in range(8):
        x = (x * 1.0000003 + 0.000001 * (node + 1)) % 1.0
    state[node] = x


def benchmark_case(total_nodes: int, affected_fraction: float, branch_size: int | None = None) -> ScaleResult:
    if not 0 < affected_fraction <= 1:
        raise ValueError("affected_fraction must be in (0,1]")
    target = max(1, int(round(total_nodes * affected_fraction)))
    branch_size = branch_size or target
    branch_size = max(1, min(branch_size, total_nodes))
    children, roots = build_chain_forest(total_nodes, branch_size)
    root = roots[0]
    affected = descendants(children, root)[:target]

    state_inc = [0.123456] * total_nodes
    t0 = perf_counter()
    for node in affected:
        _work(node, state_inc)
    inc = perf_counter() - t0

    state_full = [0.123456] * total_nodes
    t1 = perf_counter()
    for node in range(total_nodes):
        _work(node, state_full)
    full = perf_counter() - t1

    speedup = full / inc if inc > 0 else float("inf")
    return ScaleResult(
        total_nodes=total_nodes,
        affected_nodes=len(affected),
        affected_fraction=len(affected) / total_nodes,
        incremental_seconds=inc,
        full_seconds=full,
        speedup=speedup,
        touched_ratio=len(affected) / total_nodes,
    )


def benchmark_grid(sizes=(1_000, 10_000, 100_000), fractions=(0.001, 0.01, 0.10, 0.50)) -> list[ScaleResult]:
    return [benchmark_case(n, f) for n in sizes for f in fractions]
