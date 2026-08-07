from memoria_resolutiva.stability_map import build_stability_map, robust_points


def test_stability_map_builds_full_grid():
    points = build_stability_map(
        seeds=20,
        sample_grid=(10, 100),
        decay_grid=(0.3, 0.9),
        noise_grid=(0.0, 0.25),
    )
    assert len(points) == 3 * 2 * 2 * 2
    assert all(0.0 <= p.detection_rate <= 1.0 for p in points)
    assert all(0.0 <= p.exact_detection_rate <= 1.0 for p in points)
    assert all(0.0 <= p.false_alarm_rate <= 1.0 for p in points)


def test_robust_filter_is_stricter_than_full_map():
    points = build_stability_map(
        seeds=50,
        sample_grid=(10, 100),
        decay_grid=(0.3, 0.9, 1.5),
        noise_grid=(0.0, 0.25),
    )
    robust = robust_points(points, min_exact=0.9, max_false_alarm=0.1, max_mean_delay=0.5)
    assert len(robust) <= len(points)
    assert all(p.exact_detection_rate >= 0.9 for p in robust)
    assert all(p.false_alarm_rate <= 0.1 for p in robust)
