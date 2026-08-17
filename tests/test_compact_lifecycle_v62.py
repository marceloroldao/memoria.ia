from memoria_resolutiva.compact_lifecycle import CompactMemoryLifecycle
from memoria_resolutiva.memory_lifecycle import MemoryLifecycle


def exercise(factory):
    m = factory()
    for _ in range(8):
        m.support("x")
    before = (m.active_depth("x"), m.historical_depth("x"), m.snapshot("x"))
    for _ in range(16):
        m.contradict("x")
    after_contradiction = (m.active_depth("x"), m.historical_depth("x"), m.snapshot("x"))
    for _ in range(8):
        m.support("x")
    after_reactivation = (m.active_depth("x"), m.historical_depth("x"), m.snapshot("x"))
    return before, after_contradiction, after_reactivation


def test_compact_matches_full_functional_lifecycle_state():
    full = exercise(lambda: MemoryLifecycle(levels=5))
    compact = exercise(lambda: CompactMemoryLifecycle(levels=5))
    assert compact == full


def test_compact_records_transitions_not_every_event():
    m = CompactMemoryLifecycle(levels=5)
    for _ in range(64):
        m.support("x")
    assert m.transition_count("x") <= 5
