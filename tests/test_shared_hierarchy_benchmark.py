from benchmarks.shared_hierarchy import run_shared_hierarchy


def test_shared_hierarchy_invalidates_only_dependent_upper_branch():
    result = run_shared_hierarchy()

    assert result.branch_a_before is True
    assert result.branch_b_before is True
    assert result.root_a_before is True
    assert result.root_b_before is True

    assert result.branch_a_after is False
    assert result.branch_b_after is True
    assert result.root_a_after is False
    assert result.root_b_after is True
