from memoria_resolutiva.stress_v55 import run_stress


def test_stress_runs_and_reports_finite_metrics():
    m = run_stress(events=2000, items=200, seed=7)
    assert m.events == 2000
    assert m.items == 200
    assert m.elapsed_s >= 0.0
    assert m.mean_latency_us >= 0.0
    assert m.peak_memory_mb >= 0.0


def test_historical_depth_not_below_active_depth_on_average():
    m = run_stress(events=5000, items=300, seed=11)
    assert m.mean_historical_depth >= m.mean_active_depth


def test_repeatability_of_structural_metrics_with_same_seed():
    a = run_stress(events=3000, items=250, seed=42)
    b = run_stress(events=3000, items=250, seed=42)
    assert a.mean_active_depth == b.mean_active_depth
    assert a.mean_historical_depth == b.mean_historical_depth
