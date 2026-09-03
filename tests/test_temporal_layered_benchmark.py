from benchmarks.temporal_layered import run_temporal_layered


def test_temporal_layered_policy_excludes_stale_facts_over_time():
    result = run_temporal_layered()
    assert result.layered_final_stale_items == 0
    assert result.flat_final_stale_items > result.layered_final_stale_items


def test_temporal_layered_policy_compresses_repeated_pattern_context():
    result = run_temporal_layered()
    assert result.flat_final_pattern_context_items >= 2
    assert result.layered_final_pattern_context_items == 1
    assert result.final_context_reduction > 0.0


def test_temporal_curve_never_reintroduces_superseded_items_as_factual():
    result = run_temporal_layered()
    assert all(point.layered_stale_items == 0 for point in result.points)
