from memoria_resolutiva.intervention_consequence_v2 import InterventionConsequenceMemory
from memoria_resolutiva.structural_intervention_transfer_v2 import (
    intervention_key,
    resolve_structural_intervention,
)


def _memory() -> InterventionConsequenceMemory:
    memory = InterventionConsequenceMemory()

    # Literal space A.
    memory.ingest_episode(("a:0", "a:1"), "act:a", ("a:new",), ("a:0", "a:new"))
    memory.ingest_episode(("a:2", "a:3"), "act:b", ("a:new2",), ("a:2", "a:new2"))

    # Same structural regime, fully disjoint literal space B.
    memory.ingest_episode(("b:0", "b:1"), "act:c", ("b:new",), ("b:0", "b:new"))
    memory.ingest_episode(("b:2", "b:3"), "act:d", ("b:new2",), ("b:2", "b:new2"))
    return memory


def test_disjoint_literal_spaces_share_structural_intervention_key():
    a = intervention_key(("a:0", "a:1"), "act:a")
    b = intervention_key(("held:0", "held:1"), "held:act")
    assert a == b


def test_structural_consequence_transfers_without_inventing_literal_future():
    memory = _memory()
    result = resolve_structural_intervention(
        memory,
        ("held:0", "held:1"),
        "held:act",
    )
    assert result.resolved is True
    assert result.ambiguous is False
    assert len(result.patterns) == 1
    pattern = result.patterns[0]
    assert pattern.consequence_pattern == ("N0",)
    assert pattern.next_state_pattern == ("S0", "N0")
    # The held-out literal future is deliberately absent: only structure transfers.
    assert "held:" not in repr(pattern)


def test_intervention_reusing_state_component_is_not_equivalent_to_novel_action():
    novel = intervention_key(("s0", "s1"), "action")
    reused = intervention_key(("s0", "s1"), "s1")
    assert novel != reused


def test_competing_structural_consequences_remain_ambiguous():
    memory = _memory()
    memory.ingest_episode(("c:0", "c:1"), "act:e", ("c:0",), ("c:0", "c:1"))
    memory.ingest_episode(("c:2", "c:3"), "act:f", ("c:2",), ("c:2", "c:3"))

    result = resolve_structural_intervention(memory, ("held:0", "held:1"), "held:act")
    assert result.resolved is False
    assert result.ambiguous is True
    assert len(result.patterns) == 2


def test_single_episode_does_not_establish_structural_consequence():
    memory = InterventionConsequenceMemory()
    memory.ingest_episode(("a", "b"), "act", ("new",), ("a", "new"))
    result = resolve_structural_intervention(memory, ("x", "y"), "other-act")
    assert result.resolved is False
    assert result.ambiguous is False
    assert result.reason == "insufficient-structural-support"


def test_state_equality_topology_blocks_false_transfer():
    memory = _memory()
    result = resolve_structural_intervention(memory, ("held:same", "held:same"), "held:act")
    # Immediate state duplicates collapse to one address, producing a different key.
    assert result.resolved is False


def test_query_is_read_only_and_restart_deterministic():
    memory = _memory()
    before = memory.snapshot()
    r1 = resolve_structural_intervention(memory, ("held:0", "held:1"), "held:act")
    assert memory.snapshot() == before

    restored = InterventionConsequenceMemory.restore(before)
    r2 = resolve_structural_intervention(restored, ("held:0", "held:1"), "held:act")
    assert r1 == r2
