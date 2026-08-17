from memoria_resolutiva.statistical_evaluation import summarize


def test_summarize_single_value_has_zero_spread():
    mu, sd, ci = summarize([2.5])
    assert mu == 2.5
    assert sd == 0.0
    assert ci == 0.0


def test_summarize_multiple_values_returns_positive_spread():
    mu, sd, ci = summarize([1.0, 2.0, 3.0, 4.0])
    assert mu == 2.5
    assert sd > 0.0
    assert ci > 0.0


def test_more_runs_reduce_ci_for_same_sample_pattern():
    _, _, ci_small = summarize([1.0, 2.0, 1.0, 2.0])
    _, _, ci_large = summarize([1.0, 2.0, 1.0, 2.0] * 4)
    assert ci_large < ci_small
