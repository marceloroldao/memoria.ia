from memoria_resolutiva.structural_equivalence_v2 import ConvergenceEvent, StructuralEquivalenceState


def ev(sig, region, lineage, occurrence, witness, sequence):
    return ConvergenceEvent(sig, region, lineage, occurrence, witness, sequence)


def test_two_independent_witnesses_support_equivalence():
    state = StructuralEquivalenceState()
    state.observe_many([
        ev("A", "R", "L1", "a1", "W1", 1), ev("B", "R", "L2", "b1", "W1", 2),
        ev("A", "R", "L3", "a2", "W2", 3), ev("B", "R", "L4", "b2", "W2", 4),
    ])
    result = state.evaluate("A", "B")
    assert result.state == "supported"
    assert result.independent_convergence == 2
    assert result.independent_divergence == 0


def test_replay_same_event_does_not_amplify_support():
    state = StructuralEquivalenceState()
    event_a = ev("A", "R", "L1", "a1", "W1", 1)
    event_b = ev("B", "R", "L2", "b1", "W1", 2)
    for _ in range(100):
        state.observe(event_a)
        state.observe(event_b)
    result = state.evaluate("A", "B")
    assert len(state.snapshot()) == 2
    assert result.state == "candidate"
    assert result.independent_convergence == 1


def test_same_lineage_inside_witness_cannot_self_confirm():
    state = StructuralEquivalenceState()
    state.observe_many([
        ev("A", "R", "same", "a1", "W1", 1),
        ev("B", "R", "same", "b1", "W1", 2),
        ev("A", "R", "same", "a2", "W2", 3),
        ev("B", "R", "same", "b2", "W2", 4),
    ])
    assert state.evaluate("A", "B").state == "insufficient"


def test_dense_hub_without_shared_witness_never_fabricates_equivalence():
    state = StructuralEquivalenceState()
    seq = 0
    for i in range(1000):
        seq += 1
        state.observe(ev("A", "hub", f"LA{i}", f"a{i}", f"WA{i}", seq))
        seq += 1
        state.observe(ev("B", "hub", f"LB{i}", f"b{i}", f"WB{i}", seq))
    result = state.evaluate("A", "B")
    assert result.state == "insufficient"
    assert result.independent_convergence == 0


def test_independent_divergence_revokes_previously_supported_candidate():
    state = StructuralEquivalenceState()
    state.observe_many([
        ev("A", "R", "L1", "a1", "W1", 1), ev("B", "R", "L2", "b1", "W1", 2),
        ev("A", "R", "L3", "a2", "W2", 3), ev("B", "R", "L4", "b2", "W2", 4),
    ])
    assert state.evaluate("A", "B").state == "supported"

    state.observe_many([
        ev("A", "X", "L5", "a3", "W3", 5), ev("B", "Y", "L6", "b3", "W3", 6),
        ev("A", "X", "L7", "a4", "W4", 7), ev("B", "Y", "L8", "b4", "W4", 8),
    ])
    result = state.evaluate("A", "B")
    assert result.state == "contradicted"
    assert result.independent_convergence == 2
    assert result.independent_divergence == 2


def test_query_is_read_only():
    state = StructuralEquivalenceState()
    state.observe_many([
        ev("A", "R", "L1", "a1", "W1", 1), ev("B", "R", "L2", "b1", "W1", 2),
    ])
    before = state.snapshot()
    for _ in range(100):
        state.evaluate("A", "B")
    assert state.snapshot() == before


def test_conflicting_supported_equivalences_remain_separate_hypotheses():
    state = StructuralEquivalenceState()
    state.observe_many([
        ev("A", "R1", "L1", "a1", "W1", 1), ev("B", "R1", "L2", "b1", "W1", 2),
        ev("A", "R1", "L3", "a2", "W2", 3), ev("B", "R1", "L4", "b2", "W2", 4),
        ev("A", "R2", "L5", "a3", "W3", 5), ev("C", "R2", "L6", "c1", "W3", 6),
        ev("A", "R2", "L7", "a4", "W4", 7), ev("C", "R2", "L8", "c2", "W4", 8),
    ])
    ab = state.evaluate("A", "B")
    ac = state.evaluate("A", "C")
    assert ab.state == "supported"
    assert ac.state == "supported"
    assert ab.shared_terminal_regions != ac.shared_terminal_regions
