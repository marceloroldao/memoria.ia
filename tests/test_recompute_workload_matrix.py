from benchmarks.recompute_workload_matrix import recommendation_table, run_matrix


def test_all_workload_strategies_preserve_exact_snapshots():
    matrix = run_matrix()
    for strategies in matrix.values():
        for summary in strategies.values():
            assert summary.final_snapshot_equal


def test_sparse_profile_stays_incremental_for_all_policies():
    matrix = run_matrix()["sparse"]
    assert matrix["incremental"].full_batches == 0
    assert matrix["adaptive"].full_batches == 0
    assert matrix["hysteresis"].full_batches == 0
    assert matrix["incremental"].total_touched == matrix["adaptive"].total_touched
    assert matrix["incremental"].total_touched == matrix["hysteresis"].total_touched


def test_oscillating_profile_hysteresis_reduces_switches():
    matrix = run_matrix()["oscillating"]
    assert matrix["hysteresis"].mode_switches < matrix["adaptive"].mode_switches


def test_near_global_profile_selects_full_recompute_consistently():
    matrix = run_matrix()["near_global"]
    assert matrix["adaptive"].full_batches >= 6
    assert matrix["hysteresis"].full_batches >= 6


def test_recommendation_table_matches_workload_character():
    matrix = run_matrix()
    assert recommendation_table(matrix) == {
        "sparse": "incremental",
        "burst": "adaptive",
        "oscillating": "hysteresis",
        "near_global": "adaptive",
    }
