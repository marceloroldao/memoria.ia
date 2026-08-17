from memoria_resolutiva.stability_plasticity_v82 import evaluate_frontier, short_noise_survival


def test_short_noise_is_survived_for_reasonable_saturation():
    assert short_noise_survival(1.5) == 1.0


def test_frontier_metrics_are_bounded():
    row = evaluate_frontier(2.0, [(16, 16, 16), (32, 32, 32)])
    assert row.noise_survival in (0.0, 1.0)
    assert row.shift_deactivation_mean >= 0
    assert row.return_reactivation_mean >= 0
    assert 0.0 <= row.online_accuracy_mean <= 1.0
    assert 0.0 <= row.retained_history_rate <= 1.0
