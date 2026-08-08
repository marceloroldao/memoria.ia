from memoria_resolutiva.scaling_analysis import ScalingPoint, classify_exponent, empirical_time_exponents, latency_growth


def test_constant_per_event_latency_stays_flat_across_scale():
    points = [
        ScalingPoint(1_000, 0.1, 1_000_000, 100),
        ScalingPoint(10_000, 1.0, 10_000_000, 1_000),
        ScalingPoint(100_000, 10.0, 100_000_000, 10_000),
    ]
    growth = latency_growth(points)
    assert all(abs(g - 1.0) < 1e-12 for g in growth)


def test_linear_total_time_has_exponent_one():
    points = [
        ScalingPoint(1_000, 0.2, 1_000_000, 100),
        ScalingPoint(10_000, 2.0, 10_000_000, 1_000),
    ]
    alpha = empirical_time_exponents(points)[0]
    assert abs(alpha - 1.0) < 1e-12
    assert classify_exponent(alpha) == "near_linear"


def test_superlinear_growth_is_detected():
    points = [
        ScalingPoint(1_000, 0.1, 1_000_000, 100),
        ScalingPoint(10_000, 2.0, 10_000_000, 1_000),
    ]
    alpha = empirical_time_exponents(points)[0]
    assert alpha > 1.0
    assert classify_exponent(alpha) == "superlinear"


def test_bytes_per_item_is_directly_measurable():
    p = ScalingPoint(10_000, 1.0, 8_000_000, 2_000)
    assert p.bytes_per_item == 4000.0
