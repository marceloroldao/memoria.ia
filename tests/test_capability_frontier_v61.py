from memoria_resolutiva.baseline_benchmark import ChronologicalMemory, HashMemory
from memoria_resolutiva.capability_frontier import capabilities, current_score
from memoria_resolutiva.memory_lifecycle import MemoryLifecycle


def test_hash_exposes_only_basic_contract():
    c = capabilities(HashMemory())
    assert c.basic_current_score
    assert not c.historical_state
    assert not c.layer_depth


def test_chronological_exposes_raw_history_but_not_lifecycle_state():
    c = capabilities(ChronologicalMemory())
    assert c.basic_current_score
    assert c.historical_state
    assert not c.deactivation_state
    assert not c.layer_depth


def test_resolutive_exposes_full_lifecycle_contract():
    c = capabilities(MemoryLifecycle(levels=5))
    assert c.basic_current_score
    assert c.historical_state
    assert c.deactivation_state
    assert c.reactivation_history
    assert c.layer_depth


def test_current_score_is_available_for_all_baselines():
    memories = [HashMemory(), ChronologicalMemory(), MemoryLifecycle(levels=5)]
    for m in memories:
        for _ in range(4):
            m.support("x")
        assert current_score(m, "x") > 0.0
