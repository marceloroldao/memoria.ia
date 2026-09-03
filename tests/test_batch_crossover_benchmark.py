from benchmarks.batch_crossover import run_burst


def test_batch_bursts_match_full_recompute():
    for changed in (1, 8, 64, 512, 1024):
        result = run_burst(changed)
        assert result.snapshots_equal
        assert result.batch_touched <= result.full_touched


def test_small_burst_keeps_strong_locality():
    result = run_burst(8)
    assert result.batch_touched < result.full_touched * 0.10


def test_large_burst_still_avoids_unrelated_nodes():
    result = run_burst(1024)
    assert result.batch_touched < result.full_touched
