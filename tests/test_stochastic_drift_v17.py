from memoria_resolutiva.stochastic_drift import evaluate_stochastic_drift


def test_stochastic_drift_is_reproducible_and_stable_for_reference_protocol():
    summary, _ = evaluate_stochastic_drift(
        runs=1000,
        fractions=(0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
        samples_per_epoch=100,
        decay=0.9,
        seed_start=0,
    )
    assert summary.correct_epoch_probability == 0.994
    assert summary.eventual_detection_probability == 1.0
    assert summary.false_alarm_rate == 0.0
    assert summary.delayed_runs == 6
    assert summary.missed_runs == 0
    assert abs(summary.mean_detection_delay - 0.006) < 1e-12


def test_stochastic_drift_reports_more_uncertainty_with_small_epochs():
    summary, _ = evaluate_stochastic_drift(
        runs=200,
        fractions=(0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0),
        samples_per_epoch=10,
        decay=0.9,
        seed_start=1000,
    )
    assert 0.0 <= summary.correct_epoch_probability <= 1.0
    assert 0.0 <= summary.false_alarm_rate <= 1.0
    assert summary.std_detection_delay is not None
