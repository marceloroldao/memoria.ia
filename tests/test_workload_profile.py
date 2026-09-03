from memoria_resolutiva.workload_profile import classify_workload


def test_sparse_profile_prefers_incremental():
    result = classify_workload([0.03, 0.04, 0.06, 0.05, 0.08, 0.04])
    assert result.name == "sparse"
    assert result.recommended_strategy == "incremental"


def test_burst_profile_prefers_adaptive():
    result = classify_workload([0.04, 0.05, 0.72, 0.06, 0.05, 0.08])
    assert result.name == "burst"
    assert result.recommended_strategy == "adaptive"


def test_oscillating_profile_prefers_hysteresis():
    result = classify_workload([0.10, 0.52, 0.36, 0.44, 0.37, 0.43, 0.36, 0.08])
    assert result.name == "oscillating"
    assert result.recommended_strategy == "hysteresis"
    assert result.oscillation_ratio >= 0.45


def test_near_global_profile_prefers_adaptive():
    result = classify_workload([0.62, 0.71, 0.68, 0.75, 0.66])
    assert result.name == "near_global"
    assert result.recommended_strategy == "adaptive"


def test_mixed_profile_falls_back_to_adaptive():
    result = classify_workload([0.18, 0.22, 0.26, 0.31])
    assert result.name == "mixed"
    assert result.recommended_strategy == "adaptive"


def test_invalid_fraction_is_rejected():
    try:
        classify_workload([0.2, 1.1])
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError")
