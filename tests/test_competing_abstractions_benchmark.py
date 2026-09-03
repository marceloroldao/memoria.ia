from benchmarks.competing_abstractions import run_competing_abstractions


def test_competing_abstractions_invalidate_only_true_dependents():
    result = run_competing_abstractions()

    assert result.before_active == (
        "abs_pair_cats",
        "abs_pair_pets",
        "abs_other_cats",
    )
    assert result.after_active == (
        "abs_pair_pets",
        "abs_other_cats",
    )
    assert result.invalidated == ("abs_pair_cats",)
    assert result.unrelated_preserved is True
    assert result.selective_invalidation_ok is True
