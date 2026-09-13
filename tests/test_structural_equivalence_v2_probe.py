from benchmarks.structural_equivalence_v2_probe import Observation, support


def test_independent_convergence_can_support_equivalence():
    a = ("sig:a",)
    b = ("sig:b",)
    observations = [
        Observation(a, "region:r", "L1"),
        Observation(b, "region:r", "L2"),
        Observation(a, "region:r", "L3"),
        Observation(b, "region:r", "L4"),
    ]
    result = support(observations, a, b)
    assert result["supported"] is True
    assert result["independent_convergence"] >= 2


def test_repeated_same_lineage_cannot_self_confirm():
    a = ("sig:a",)
    b = ("sig:b",)
    observations = [Observation(a, "region:r", "same") for _ in range(100)]
    observations += [Observation(b, "region:r", "same") for _ in range(100)]
    result = support(observations, a, b)
    assert result["supported"] is False
    assert result["independent_convergence"] == 0


def test_single_accidental_convergence_is_insufficient():
    a = ("sig:a",)
    b = ("sig:b",)
    observations = [
        Observation(a, "region:r", "L1"),
        Observation(b, "region:r", "L2"),
    ]
    result = support(observations, a, b)
    assert result["supported"] is False
    assert result["independent_convergence"] == 1
