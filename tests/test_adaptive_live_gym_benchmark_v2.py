from memoria_resolutiva.adaptive_live_gym_benchmark_v2 import run_adaptive_world_benchmark


def test_100_cycle_structural_memory_records_persistent_ambiguity_without_temporal_regime():
    report = run_adaptive_world_benchmark(100, switch_cycle=50)
    assert report.episodes == 100
    # A and B are structurally equivalent and both are always visible candidates.
    # Pure structural memory therefore remains ambiguous rather than inventing a
    # current regime or declaring a false surprise at the switch.
    assert report.first_post_switch_surprise is None
    assert report.final_ambiguous is True
    assert report.final_resolved is False
    assert report.first_post_switch_confirmation is None
    assert report.hypothesis_reductions > 0


def test_1000_cycle_structural_memory_is_deterministic_and_exposes_same_limitation():
    a = run_adaptive_world_benchmark(1000, switch_cycle=500)
    b = run_adaptive_world_benchmark(1000, switch_cycle=500)
    assert a == b
    assert a.episodes == 1000
    assert a.first_post_switch_surprise is None
    assert a.final_ambiguous is True
    assert a.final_resolved is False


def test_invalid_benchmark_window_fails_closed():
    try:
        run_adaptive_world_benchmark(3)
    except ValueError as exc:
        assert "cycles" in str(exc)
    else:
        raise AssertionError("expected ValueError")
