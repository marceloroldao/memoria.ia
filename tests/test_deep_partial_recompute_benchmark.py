from benchmarks.deep_partial_recompute import run_deep_partial_recompute


def test_deep_partial_recompute_matches_full_with_local_work():
    result = run_deep_partial_recompute()
    assert result.total_nodes == 15
    assert result.incremental_touched == 4
    assert result.full_touched == 15
    assert result.snapshots_equal is True
    assert result.incremental_path == ("r1", "a1", "b1", "top")
    assert result.touched_reduction > 0.70
