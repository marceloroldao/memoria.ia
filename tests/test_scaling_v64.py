from memoria_resolutiva.scaling_v64 import empirical_exponent, evaluate_scale


def test_empirical_exponent_detects_linear_growth():
    p = empirical_exponent([10, 100, 1000], [20, 200, 2000])
    assert abs(p - 1.0) < 1e-12


def test_compact_scaling_evaluator_returns_positive_metrics():
    events = [[(f"x{i % 5}", True, 1.0) for i in range(100)]]
    row = evaluate_scale(events, items=5, levels=3)
    assert row.events == 100
    assert row.runs == 1
    assert row.latency_us_mean > 0
    assert row.throughput_mean > 0
    assert row.peak_bytes_mean > 0
    assert row.bytes_per_item > 0
