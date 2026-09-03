from benchmarks.architecture_ab import run_architecture_ab


def test_layered_architecture_blocks_flat_policy_failures():
    result = run_architecture_ab()

    assert result.flat_false_positives == 1
    assert result.layered_false_positives == 0
    assert result.flat_stale_facts == 1
    assert result.layered_stale_facts == 0
    assert result.flat_stale_derivations == 1
    assert result.layered_stale_derivations == 0


def test_layered_architecture_reduces_pattern_context_proxy():
    result = run_architecture_ab()

    assert result.flat_pattern_context_items == 4
    assert result.layered_pattern_context_items == 1
    assert result.pattern_context_reduction == 0.75
    assert result.layered_safety_score > result.flat_safety_score
