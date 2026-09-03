from benchmarks.layered_resources import run_resource


def test_resource_100_equivalence():
    result = run_resource(100)
    assert result.snapshots_equal
    assert result.incremental_touched < result.full_touched
    assert result.peak_heap_bytes > 0


def test_resource_1000_equivalence():
    result = run_resource(1_000)
    assert result.snapshots_equal
    assert result.incremental_touched < result.full_touched
    assert result.peak_heap_bytes > 0


def test_resource_10000_equivalence():
    result = run_resource(10_000)
    assert result.snapshots_equal
    assert result.incremental_touched < result.full_touched
    assert result.peak_heap_bytes > 0
