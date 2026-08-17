from memoria_resolutiva.calibration import brier_score, expected_calibration_error, reliability_bins


def test_perfect_binary_predictions_have_zero_brier():
    assert brier_score([0.0, 1.0, 1.0, 0.0], [0, 1, 1, 0]) == 0.0


def test_overconfident_wrong_predictions_are_penalized():
    good = brier_score([0.8, 0.2], [1, 0])
    bad = brier_score([0.99, 0.01], [0, 1])
    assert bad > good


def test_reliability_bins_report_empirical_frequency():
    p = [0.8] * 10
    y = [1] * 8 + [0] * 2
    bins = reliability_bins(p, y, bins=10)
    assert len(bins) == 1
    assert abs(bins[0].mean_confidence - 0.8) < 1e-12
    assert abs(bins[0].empirical_accuracy - 0.8) < 1e-12


def test_well_calibrated_construct_has_low_ece():
    p = [0.2] * 100 + [0.8] * 100
    y = ([1] * 20 + [0] * 80) + ([1] * 80 + [0] * 20)
    assert expected_calibration_error(p, y, bins=10) < 1e-12


def test_miscalibrated_construct_has_high_ece():
    p = [0.9] * 100
    y = [1] * 50 + [0] * 50
    assert expected_calibration_error(p, y, bins=10) >= 0.39
