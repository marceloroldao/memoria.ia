from benchmarks.layered_scale import build_balanced_graph
from memoria_resolutiva.workload_strategy import WorkloadStrategyExecutor


def _reference_after(updates):
    graph, _, _ = build_balanced_graph(100)
    graph._apply_root_updates(updates)
    graph.full_recompute()
    return graph.snapshot()


def test_sparse_profile_executes_incremental_and_preserves_equivalence():
    graph, _, _ = build_balanced_graph(100)
    executor = WorkloadStrategyExecutor()
    updates = {"r0": -1.0}
    result = executor.execute(graph, updates, [0.02, 0.03, 0.01, 0.02])
    assert result.profile.name == "sparse"
    assert result.requested_strategy == "incremental"
    assert result.executed_strategy == "incremental"
    assert not result.fallback_used
    assert graph.snapshot() == _reference_after(updates)


def test_burst_profile_executes_adaptive_and_preserves_equivalence():
    graph, _, _ = build_balanced_graph(100)
    executor = WorkloadStrategyExecutor()
    updates = {f"r{i}": -float(i + 1) for i in range(24)}
    result = executor.execute(graph, updates, [0.03, 0.04, 0.70, 0.05])
    assert result.profile.name == "burst"
    assert result.requested_strategy == "adaptive"
    assert result.executed_strategy == "adaptive"
    assert not result.fallback_used
    assert graph.snapshot() == _reference_after(updates)


def test_oscillating_profile_executes_hysteresis_and_preserves_equivalence():
    graph, _, _ = build_balanced_graph(100)
    executor = WorkloadStrategyExecutor()
    updates = {f"r{i}": -float(i + 1) for i in range(20)}
    result = executor.execute(graph, updates, [0.35, 0.48, 0.37, 0.46, 0.36, 0.47])
    assert result.profile.name == "oscillating"
    assert result.requested_strategy == "hysteresis"
    assert result.executed_strategy == "hysteresis"
    assert not result.fallback_used
    assert graph.snapshot() == _reference_after(updates)


def test_near_global_profile_executes_adaptive_and_preserves_equivalence():
    graph, _, _ = build_balanced_graph(100)
    executor = WorkloadStrategyExecutor()
    updates = {f"r{i}": -float(i + 1) for i in range(48)}
    result = executor.execute(graph, updates, [0.65, 0.72, 0.61, 0.68])
    assert result.profile.name == "near_global"
    assert result.executed_strategy == "adaptive"
    assert graph.snapshot() == _reference_after(updates)
