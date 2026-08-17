from memoria_resolutiva.compact_lifecycle import CompactMemoryLifecycle


def test_compact_lifecycle_consolidates_deconsolidates_and_reactivates():
    memory = CompactMemoryLifecycle(levels=5)
    for _ in range(32):
        memory.support("target")
    assert memory.active_depth("target") == 4
    assert memory.historical_depth("target") == 4

    for _ in range(40):
        memory.contradict("target")
    assert memory.active_depth("target") == -1
    assert memory.historical_depth("target") == 4

    for _ in range(32):
        memory.support("target")
    assert memory.active_depth("target") == 4
    assert memory.historical_depth("target") == 4


def test_layer_rates_follow_multiscale_clock_rule():
    memory = CompactMemoryLifecycle(levels=5)
    assert [memory.rate(i) for i in range(5)] == [1.0, 0.5, 0.25, 0.125, 0.0625]


def test_transition_history_is_sparse():
    memory = CompactMemoryLifecycle(levels=5)
    for _ in range(100):
        memory.support("target")
    # Each layer activates at most once during monotonic support.
    assert memory.transition_count("target") <= 5
