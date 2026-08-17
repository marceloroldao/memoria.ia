from memoria_resolutiva.scaling_benchmark import benchmark_case


def test_touched_ratio_tracks_requested_fraction():
    r = benchmark_case(10_000, 0.01)
    assert r.affected_nodes == 100
    assert abs(r.touched_ratio - 0.01) < 1e-12


def test_half_graph_update_touches_half_graph():
    r = benchmark_case(10_000, 0.50)
    assert r.affected_nodes == 5_000
    assert abs(r.touched_ratio - 0.50) < 1e-12


def test_incremental_and_full_use_same_per_node_work_model():
    small = benchmark_case(20_000, 0.01)
    large = benchmark_case(20_000, 0.50)
    # Avoid brittle timing assertions; structural work should scale with touched nodes.
    assert small.affected_nodes < large.affected_nodes
    assert small.touched_ratio < large.touched_ratio


def test_full_fraction_matches_full_recomputation_scope():
    r = benchmark_case(5_000, 1.0)
    assert r.affected_nodes == r.total_nodes
    assert r.touched_ratio == 1.0
