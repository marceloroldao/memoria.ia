from memoria_resolutiva.multi_regime_stress_v2 import run_multi_regime_stress


def test_a_b_a_regimes_switch_twice_and_preserve_both_histories():
    report = run_multi_regime_stress(segment_length=20, min_contiguous_support=2)
    assert report.cycles == 60
    assert report.switches_observed == 2
    assert report.final_regime_consequence == ("effect:a",)
    assert report.historical_hypotheses == 2
    assert report.historical_episodes == 60
    assert report.confirmations > 0


def test_single_noise_does_not_add_extra_regime_switch():
    noisy = run_multi_regime_stress(segment_length=20, min_contiguous_support=2, inject_single_noise=True)
    clean = run_multi_regime_stress(segment_length=20, min_contiguous_support=2, inject_single_noise=False)
    assert noisy.switches_observed == 2
    assert clean.switches_observed == 2
    assert noisy.final_regime_consequence == clean.final_regime_consequence == ("effect:a",)
    assert noisy.historical_hypotheses == clean.historical_hypotheses == 2


def test_three_step_contiguous_support_delays_but_does_not_prevent_reorientation():
    report = run_multi_regime_stress(segment_length=20, min_contiguous_support=3)
    assert report.switches_observed == 2
    assert report.final_regime_consequence == ("effect:a",)
    assert report.reorientations >= 4


def test_multi_regime_stress_is_deterministic():
    a = run_multi_regime_stress(segment_length=50, min_contiguous_support=2)
    b = run_multi_regime_stress(segment_length=50, min_contiguous_support=2)
    assert a == b
