from benchmarks.layered_scale import run_scale


def test_scale_100_preserves_equivalence_and_locality():
    result = run_scale(100)
    assert result.snapshots_equal
    assert result.incremental_touched == result.depth + 1
    assert result.incremental_touched < result.full_touched
    assert result.touched_reduction_ratio > 0.90


def test_scale_1000_preserves_equivalence_and_locality():
    result = run_scale(1_000)
    assert result.snapshots_equal
    assert result.incremental_touched == result.depth + 1
    assert result.touched_reduction_ratio > 0.98


def test_scale_10000_preserves_equivalence_and_locality():
    result = run_scale(10_000)
    assert result.snapshots_equal
    assert result.incremental_touched == result.depth + 1
    assert result.touched_reduction_ratio > 0.99
