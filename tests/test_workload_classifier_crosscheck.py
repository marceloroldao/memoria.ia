from benchmarks.recompute_workload_matrix import workload_profiles
from memoria_resolutiva.workload_classifier import classify_workload


EXPECTED = {
    "sparse": ("sparse", "incremental"),
    "burst": ("burst", "adaptive"),
    "oscillating": ("oscillating", "hysteresis"),
    "near_global": ("near_global", "adaptive"),
}


def _fractions_for_counts(counts: list[int]) -> list[float]:
    # Matrix uses a balanced graph with 1,023 nodes and 512 roots. Use the same
    # deterministic approximation employed by the workload shapes: root-count
    # density is monotonic with affected-node density and preserves profile shape.
    return [count / 512.0 for count in counts]


def test_classifier_matches_all_matrix_profiles():
    for name, counts in workload_profiles().items():
        result = classify_workload(_fractions_for_counts(counts))
        expected_profile, expected_strategy = EXPECTED[name]
        assert result.profile == expected_profile, (name, result)
        assert result.recommended_strategy == expected_strategy, (name, result)
