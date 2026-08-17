from memoria_resolutiva.stochastic_stability_v83 import evaluate, run_seed


def test_run_seed_returns_bounded_metrics():
    survival, accuracy, history, reactivated = run_seed(1.25, seed=11, steps=200, noise_p=0.1)
    assert 0.0 <= survival <= 1.0
    assert 0.0 <= accuracy <= 1.0
    assert isinstance(history, bool)
    assert isinstance(reactivated, bool)


def test_evaluate_preserves_history_in_controlled_noise():
    r = evaluate(1.25, seeds=(11, 23, 37), noise_p=0.05)
    assert r.history_retention_rate == 1.0
    assert r.final_reactivation_rate == 1.0
