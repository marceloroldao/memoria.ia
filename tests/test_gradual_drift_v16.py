from memoria_resolutiva.gradual_drift import evaluate_gradual_drift


def test_gradual_drift_detects_majority_crossover_without_false_alarm():
    fractions = [0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0]
    report = evaluate_gradual_drift(fractions, decay=0.9, samples_per_epoch=100)

    assert report.expected_change_epoch == 4
    assert report.detected_change_epoch == 4
    assert report.detection_delay == 0
    assert report.false_alarms == 0
    assert report.epochs[0].current_winner == "ponte"
    assert report.epochs[-1].current_winner == "tunel"


def test_no_change_stream_produces_no_detection():
    report = evaluate_gradual_drift([0.0, 0.1, 0.2, 0.3, 0.4], decay=0.9)
    assert report.expected_change_epoch is None
    assert report.detected_change_epoch is None
    assert report.detection_delay is None
    assert report.false_alarms == 0
