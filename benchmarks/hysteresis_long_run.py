"""Long-run benchmark: single-threshold adaptive recompute vs hysteresis.

The workload repeatedly oscillates around the decision boundary. Both
strategies must preserve exact snapshots; the benchmark records mode switches
and cumulative touched nodes so the stability/work tradeoff is explicit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json

from benchmarks.layered_scale import build_balanced_graph
from memoria_resolutiva.adaptive_recompute import HysteresisRecomputePolicy


@dataclass(frozen=True)
class StrategyResult:
    name: str
    batches: int
    mode_switches: int
    total_touched: int
    final_snapshot_equal: bool
    modes: tuple[str, ...]
    affected_fractions: tuple[float, ...]


def _updates(count: int, step: int) -> dict[str, float]:
    base = -1000.0 - (step * 100.0)
    return {f"r{i}": base - i for i in range(count)}


def _switches(modes: list[str]) -> int:
    return sum(a != b for a, b in zip(modes, modes[1:]))


def workload_counts(cycles: int = 8) -> list[int]:
    # On a ~127-node balanced graph these batches straddle the adaptive
    # boundary: low -> medium -> high -> medium -> low.
    pattern = [1, 20, 28, 32, 28, 20]
    return pattern * cycles


def run_single_threshold(*, cycles: int = 8, threshold: float = 0.40) -> StrategyResult:
    graph, _, _ = build_balanced_graph(100)
    reference, _, _ = build_balanced_graph(100)
    modes: list[str] = []
    fractions: list[float] = []
    total_touched = 0

    for step, count in enumerate(workload_counts(cycles)):
        updates = _updates(count, step)
        decision = graph.update_roots_adaptive(updates, full_threshold=threshold)
        modes.append(decision.mode)
        fractions.append(decision.affected_fraction)
        total_touched += len(decision.touched)

        reference._apply_root_updates(updates)
        reference.full_recompute()
        assert graph.snapshot() == reference.snapshot()

    return StrategyResult(
        name="single_threshold",
        batches=len(modes),
        mode_switches=_switches(modes),
        total_touched=total_touched,
        final_snapshot_equal=graph.snapshot() == reference.snapshot(),
        modes=tuple(modes),
        affected_fractions=tuple(fractions),
    )


def run_hysteresis(
    *,
    cycles: int = 8,
    enter_full_threshold: float = 0.45,
    exit_full_threshold: float = 0.30,
) -> StrategyResult:
    graph, _, _ = build_balanced_graph(100)
    reference, _, _ = build_balanced_graph(100)
    policy = HysteresisRecomputePolicy(
        enter_full_threshold=enter_full_threshold,
        exit_full_threshold=exit_full_threshold,
    )
    modes: list[str] = []
    fractions: list[float] = []
    total_touched = 0

    for step, count in enumerate(workload_counts(cycles)):
        updates = _updates(count, step)
        decision = policy.apply(graph, updates)
        modes.append(decision.mode)
        fractions.append(decision.affected_fraction)
        total_touched += len(decision.touched)

        reference._apply_root_updates(updates)
        reference.full_recompute()
        assert graph.snapshot() == reference.snapshot()

    return StrategyResult(
        name="hysteresis",
        batches=len(modes),
        mode_switches=_switches(modes),
        total_touched=total_touched,
        final_snapshot_equal=graph.snapshot() == reference.snapshot(),
        modes=tuple(modes),
        affected_fractions=tuple(fractions),
    )


def run_comparison(*, cycles: int = 8) -> dict[str, object]:
    single = run_single_threshold(cycles=cycles)
    hysteresis = run_hysteresis(cycles=cycles)
    return {
        "single_threshold": asdict(single),
        "hysteresis": asdict(hysteresis),
        "switch_reduction": 1.0 - (hysteresis.mode_switches / single.mode_switches)
        if single.mode_switches
        else 0.0,
        "touched_ratio_hysteresis_vs_single": hysteresis.total_touched / single.total_touched,
    }


if __name__ == "__main__":
    print(json.dumps(run_comparison(), indent=2, sort_keys=True))
