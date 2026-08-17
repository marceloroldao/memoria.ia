from memoria_resolutiva.resolutive_calibration import evaluate_resolutive_calibration, synthetic_resolutive_trials


def test_trials_are_reproducible():
    a = synthetic_resolutive_trials(seed=7, n=100)
    b = synthetic_resolutive_trials(seed=7, n=100)
    assert a == b


def test_confidences_are_valid_probabilities():
    p, y = synthetic_resolutive_trials(seed=1, n=200)
    assert all(0.0 <= value <= 1.0 for value in p)
    assert set(y) <= {0, 1}


def test_reference_protocol_has_useful_discrimination_but_imperfect_calibration():
    result = evaluate_resolutive_calibration(seed=123, n=2000, bins=10)
    assert result.accuracy >= 0.85
    # The purpose of v0.37 is to expose that raw confidence is not yet calibrated.
    assert result.ece > 0.10
    assert result.max_confidence - result.min_confidence < 0.40
