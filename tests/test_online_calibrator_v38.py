from memoria_resolutiva.calibration import brier_score, expected_calibration_error
from memoria_resolutiva.online_calibrator import OnlineHistogramCalibrator


def test_calibrator_starts_identity_with_little_data():
    c = OnlineHistogramCalibrator(bins=10)
    assert c.calibrate(0.57) == 0.57


def test_calibrator_learns_empirical_frequency_online():
    c = OnlineHistogramCalibrator(bins=10)
    for _ in range(18):
        c.update(0.55, 1)
    for _ in range(2):
        c.update(0.55, 0)
    p = c.calibrate(0.55, min_count=8)
    assert 0.80 < p < 0.95


def test_prequential_calibration_improves_miscalibrated_stream():
    raw = ([0.55] * 100) + ([0.45] * 100)
    outcomes = ([1] * 90 + [0] * 10) + ([1] * 10 + [0] * 90)
    c = OnlineHistogramCalibrator(bins=20)
    calibrated = []
    for p, y in zip(raw, outcomes):
        calibrated.append(c.calibrate(p, min_count=8))
        c.update(p, y)
    assert brier_score(calibrated, outcomes) < brier_score(raw, outcomes)
    assert expected_calibration_error(calibrated, outcomes, bins=10) < expected_calibration_error(raw, outcomes, bins=10)


def test_update_is_incremental():
    c = OnlineHistogramCalibrator(bins=10)
    before = sum(c.counts())
    c.update(0.4, 1)
    after = sum(c.counts())
    assert after - before == 1.0
