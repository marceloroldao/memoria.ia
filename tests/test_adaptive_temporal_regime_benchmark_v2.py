from memoria_resolutiva.adaptive_temporal_regime_benchmark_v2 import run_temporal_regime_benchmark


def test_100_cycle_regime_switch_detects_surprise_and_reorients_to_b():
    report = run_temporal_regime_benchmark(100, switch_cycle=50)
    assert report.historical_episodes == 100
    assert report.first_post_switch_surprise == 50
    assert report.regime_switch_cycle == 51
    assert report.first_post_switch_confirmation == 52
    assert report.adaptation_latency == 2
    assert report.final_regime_consequence == ("effect:b",)
    assert report.regime_switches == 1
    assert report.total_surprises >= 2
    assert report.reorientations >= 2


def test_1000_cycle_regime_switch_is_deterministic_and_preserves_history():
    a = run_temporal_regime_benchmark(1000, switch_cycle=500)
    b = run_temporal_regime_benchmark(1000, switch_cycle=500)
    assert a == b
    assert a.historical_episodes == 1000
    assert a.first_post_switch_surprise == 500
    assert a.regime_switch_cycle == 501
    assert a.first_post_switch_confirmation == 502
    assert a.adaptation_latency == 2
    assert a.final_regime_consequence == ("effect:b",)


def test_temporal_regime_does_not_change_without_contiguous_support():
    report = run_temporal_regime_benchmark(
        30,
        switch_cycle=15,
        min_contiguous_support=3,
    )
    assert report.first_post_switch_surprise == 15
    assert report.regime_switch_cycle == 17
    assert report.first_post_switch_confirmation == 18
    assert report.adaptation_latency == 3


def test_invalid_temporal_benchmark_window_fails_closed():
    try:
        run_temporal_regime_benchmark(5)
    except ValueError as exc:
        assert "cycles" in str(exc)
    else:
        raise AssertionError("expected ValueError")
