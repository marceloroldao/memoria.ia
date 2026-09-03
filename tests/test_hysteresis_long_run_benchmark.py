from benchmarks.hysteresis_long_run import run_comparison


def test_hysteresis_reduces_mode_switching_and_preserves_equivalence():
    result = run_comparison(cycles=8)
    single = result["single_threshold"]
    hysteresis = result["hysteresis"]

    assert single["final_snapshot_equal"]
    assert hysteresis["final_snapshot_equal"]
    assert hysteresis["mode_switches"] < single["mode_switches"]
    assert result["switch_reduction"] >= 0.40


def test_hysteresis_work_overhead_is_measured_and_bounded():
    result = run_comparison(cycles=8)

    # Hysteresis may intentionally remain in full mode inside its deadband.
    # The benchmark therefore records rather than hides that cost, while
    # guarding against pathological work amplification.
    assert result["touched_ratio_hysteresis_vs_single"] > 0.0
    assert result["touched_ratio_hysteresis_vs_single"] <= 2.0
