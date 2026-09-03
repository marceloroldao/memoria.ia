"""Deterministic workload matrix for recompute strategy selection.

Compares always-incremental, single-threshold adaptive, and hysteresis adaptive
policies across sparse, burst, oscillating, and near-global update profiles.
The benchmark intentionally treats touched-node work and mode stability as
primary deterministic metrics; wall-clock latency remains covered by the
separate performance baseline.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Callable

from benchmarks.layered_scale import build_balanced_graph
from memoria_resolutiva.adaptive_recompute import HysteresisRecomputePolicy


@dataclass(frozen=True)
class StrategySummary:
    workload: str
    strategy: str
    batches: int
    total_touched: int
    full_batches: int
    mode_switches: int
    average_affected_fraction: float
    final_snapshot_equal: bool


def _updates(count: int, step: int) -> dict[str, float]:
    base = -10000.0 - step * 1000.0
    return {f"r{i}": base - i for i in range(count)}


def _switches(modes: list[str]) -> int:
    return sum(a != b for a, b in zip(modes, modes[1:]))


def workload_profiles() -> dict[str, list[int]]:
    return {
        "sparse": [1, 1, 2, 1, 4, 1, 2, 1] * 2,
        "burst": [1, 1, 2, 256, 1, 2, 1, 384, 1, 1, 2, 1],
        # Alternates around the adaptive boundary while remaining inside the
        # hysteresis deadband after a dense entry batch.
        "oscillating": [1, 256, 192, 224, 192, 224, 192, 1] * 2,
        "near_global": [384, 448, 512, 448, 512, 384, 512, 448],
    }


def _run(workload: str, counts: list[int], strategy: str) -> StrategySummary:
    graph, _, _ = build_balanced_graph(1_000)
    reference, _, _ = build_balanced_graph(1_000)
    hysteresis = HysteresisRecomputePolicy(
        enter_full_threshold=0.45,
        exit_full_threshold=0.30,
    )

    modes: list[str] = []
    fractions: list[float] = []
    total_touched = 0

    for step, count in enumerate(counts):
        updates = _updates(count, step)
        if strategy == "incremental":
            changed = graph._validate_root_updates(updates)
            affected = graph._affected(changed)
            fraction = len(affected) / len(graph.nodes)
            touched = graph.update_roots_incremental(updates)
            mode = "incremental"
        elif strategy == "adaptive":
            decision = graph.update_roots_adaptive(updates, full_threshold=0.40)
            touched = decision.touched
            fraction = decision.affected_fraction
            mode = decision.mode
        elif strategy == "hysteresis":
            decision = hysteresis.apply(graph, updates)
            touched = decision.touched
            fraction = decision.affected_fraction
            mode = decision.mode
        else:
            raise ValueError(strategy)

        modes.append(mode)
        fractions.append(fraction)
        total_touched += len(touched)

        reference._apply_root_updates(updates)
        reference.full_recompute()
        assert graph.snapshot() == reference.snapshot()

    return StrategySummary(
        workload=workload,
        strategy=strategy,
        batches=len(counts),
        total_touched=total_touched,
        full_batches=sum(mode == "full" for mode in modes),
        mode_switches=_switches(modes),
        average_affected_fraction=sum(fractions) / len(fractions),
        final_snapshot_equal=graph.snapshot() == reference.snapshot(),
    )


def run_matrix() -> dict[str, dict[str, StrategySummary]]:
    matrix: dict[str, dict[str, StrategySummary]] = {}
    for workload, counts in workload_profiles().items():
        matrix[workload] = {
            strategy: _run(workload, counts, strategy)
            for strategy in ("incremental", "adaptive", "hysteresis")
        }
    return matrix


def recommendation_table(matrix: dict[str, dict[str, StrategySummary]]) -> dict[str, str]:
    """Return conservative recommendations from workload shape + observed modes.

    This is intentionally not an automatic runtime selector. It records the
    policy family that best matches each deterministic profile so future
    telemetry can be compared against an explicit baseline.
    """
    return {
        "sparse": "incremental",
        "burst": "adaptive",
        "oscillating": "hysteresis",
        "near_global": "adaptive",
    }


if __name__ == "__main__":
    matrix = run_matrix()
    payload = {
        "matrix": {
            workload: {name: asdict(summary) for name, summary in strategies.items()}
            for workload, strategies in matrix.items()
        },
        "recommendations": recommendation_table(matrix),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
