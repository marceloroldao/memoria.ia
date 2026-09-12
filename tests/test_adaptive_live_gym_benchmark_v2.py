from memoria_resolutiva.adaptive_live_gym_benchmark_v2 import run_adaptive_world_benchmark


def test_100_cycle_regime_switch_records_current_non_adaptation_without_hiding_it():
    report = run_adaptive_world_benchmark(100, switch_cycle=50)
    assert report.episodes == 100
    assert report.first_post_switch_surprise == 50
    # Persistent memory preserves both independently supported regimes. Without a
    # separate current-state continuity mechanism, the resolver should not pretend
    # that historical A disappeared; both A and B remain structurally supported.
    assert report.final_ambiguous is True
    assert report.final_resolved is False
    assert report.first_post_switch_confirmation is None
    assert report.hypothesis_reductions > 0


def test_1000_cycle_regime_switch_is_deterministic_and_exposes_same_limitation():
    a = run_adaptive_world_benchmark(1000, switch_cycle=500)
    b = run_adaptive_world_benchmark(1000, switch_cycle=500)
    assert a == b
    assert a.episodes == 1000
    assert a.first_post_switch_surprise == 500
    assert a.final_ambiguous is True
    assert a.final_resolved is False


def test_invalid_benchmark_window_fails_closed():
    try:
        run_adaptive_world_benchmark(3)
    except ValueError as exc:
        assert "cycles" in str(exc)
    else:
        raise AssertionError("expected ValueError")
