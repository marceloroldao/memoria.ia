from memoria_resolutiva.compact_lifecycle import CompactMemoryLifecycle
from memoria_resolutiva.packed_lifecycle import PackedMemoryLifecycle


def drive(memory):
    for _ in range(32):
        memory.support("x")
    consolidated = (memory.active_depth("x"), memory.historical_depth("x"), memory.snapshot("x"))
    for _ in range(40):
        memory.contradict("x")
    deconsolidated = (memory.active_depth("x"), memory.historical_depth("x"), memory.snapshot("x"))
    for _ in range(32):
        memory.support("x")
    reactivated = (memory.active_depth("x"), memory.historical_depth("x"), memory.snapshot("x"))
    return consolidated, deconsolidated, reactivated, memory.transition_count("x")


def test_packed_matches_compact_functional_state():
    compact = drive(CompactMemoryLifecycle(levels=5))
    packed = drive(PackedMemoryLifecycle(levels=5))
    assert packed[:3] == compact[:3]
    assert packed[3] == compact[3]


def test_packed_preserves_layer_clock_rule():
    m = PackedMemoryLifecycle(levels=5)
    assert [m.rate(i) for i in range(5)] == [1.0, 0.5, 0.25, 0.125, 0.0625]


def test_packed_records_last_transition_and_counts():
    m = PackedMemoryLifecycle(levels=3)
    m.support("x")
    s0 = m._states("x")[0]
    assert s0.activation_count == 1
    assert s0.last_transition_kind == 1
    m.contradict("x")
    assert s0.deactivation_count == 1
    assert s0.last_transition_kind == 2
