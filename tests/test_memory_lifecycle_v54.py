from memoria_resolutiva.memory_lifecycle import MemoryLifecycle


def test_persistent_pattern_reaches_deeper_than_transient_noise():
    m = MemoryLifecycle(levels=5)
    for _ in range(40):
        m.support("signal")
    m.support("noise")
    assert m.active_depth("signal") > m.active_depth("noise")


def test_contradiction_reduces_active_depth_but_preserves_history():
    m = MemoryLifecycle(levels=5)
    for _ in range(40):
        m.support("x")
    before = m.active_depth("x")
    historical = m.historical_depth("x")
    for _ in range(40):
        m.contradict("x")
    assert m.active_depth("x") < before
    assert m.historical_depth("x") == historical


def test_recurrence_can_reactivate_old_memory():
    m = MemoryLifecycle(levels=4)
    for _ in range(32):
        m.support("x")
    for _ in range(32):
        m.contradict("x")
    weakened = m.active_depth("x")
    for _ in range(32):
        m.support("x")
    assert m.active_depth("x") > weakened


def test_deeper_layers_change_more_slowly():
    m = MemoryLifecycle(levels=4)
    for _ in range(16):
        m.support("x")
    snap = m.snapshot("x")
    strengths = [row[1] for row in snap]
    assert strengths[0] > strengths[1] > strengths[2] > strengths[3]


def test_global_time_is_monotonic_across_support_and_contradiction():
    m = MemoryLifecycle()
    m.support("x")
    t1 = m.time
    m.contradict("x")
    assert m.time == t1 + 1
