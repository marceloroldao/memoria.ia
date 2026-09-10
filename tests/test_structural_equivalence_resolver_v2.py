from memoria_resolutiva.structural_equivalence_resolver_v2 import resolve_via_structural_equivalence
from memoria_resolutiva.structural_equivalence_v2 import ConvergenceEvent, StructuralEquivalenceState


def ev(sig, region, lineage, occurrence, witness, sequence):
    return ConvergenceEvent(sig, region, lineage, occurrence, witness, sequence)


def supported_state(left="Q", right="B", region="R"):
    state = StructuralEquivalenceState()
    state.observe_many([
        ev(left, region, "L1", "l1", "W1", 1), ev(right, region, "L2", "r1", "W1", 2),
        ev(left, region, "L3", "l2", "W2", 3), ev(right, region, "L4", "r2", "W2", 4),
    ])
    return state


def test_supported_equivalence_can_bridge_unresolved_signature():
    state = supported_state()
    before = state.snapshot()
    result = resolve_via_structural_equivalence(
        query_signature_id="Q", equivalence_state=state,
        signature_terminals={"B": "target"}, known_signature_ids=["B"]
    )
    assert result.resolved is True
    assert result.terminal_region_id == "target"
    assert result.source == "structural-equivalence"
    assert result.equivalent_signature_ids == ("B",)
    assert result.supporting_witnesses == ("W1", "W2")
    assert state.snapshot() == before


def test_direct_evidence_always_precedes_equivalence():
    state = supported_state()
    result = resolve_via_structural_equivalence(
        query_signature_id="Q", equivalence_state=state,
        signature_terminals={"B": "wrong"}, known_signature_ids=["B"],
        direct_terminal_region_id="direct-target",
    )
    assert result.resolved is True
    assert result.terminal_region_id == "direct-target"
    assert result.source == "direct"
    assert result.equivalent_signature_ids == ()


def test_single_witness_candidate_cannot_resolve():
    state = StructuralEquivalenceState()
    state.observe_many([
        ev("Q", "R", "L1", "q1", "W1", 1),
        ev("B", "R", "L2", "b1", "W1", 2),
    ])
    result = resolve_via_structural_equivalence(
        query_signature_id="Q", equivalence_state=state,
        signature_terminals={"B": "target"}, known_signature_ids=["B"]
    )
    assert result.resolved is False
    assert result.source == "unresolved"


def test_contradicted_equivalence_cannot_resolve():
    state = supported_state()
    state.observe_many([
        ev("Q", "X", "L5", "q3", "W3", 5), ev("B", "Y", "L6", "b3", "W3", 6),
        ev("Q", "X", "L7", "q4", "W4", 7), ev("B", "Y", "L8", "b4", "W4", 8),
    ])
    assert state.evaluate("Q", "B").state == "contradicted"
    result = resolve_via_structural_equivalence(
        query_signature_id="Q", equivalence_state=state,
        signature_terminals={"B": "target"}, known_signature_ids=["B"]
    )
    assert result.resolved is False
    assert result.source == "unresolved"


def test_conflicting_supported_routes_fail_closed():
    state = StructuralEquivalenceState()
    state.observe_many([
        ev("Q", "X", "Q1", "q1", "AB1", 1), ev("B", "X", "B1", "b1", "AB1", 2),
        ev("Q", "X", "Q2", "q2", "AB2", 3), ev("B", "X", "B2", "b2", "AB2", 4),
        ev("Q", "Y", "Q3", "q3", "AC1", 5), ev("C", "Y", "C1", "c1", "AC1", 6),
        ev("Q", "Y", "Q4", "q4", "AC2", 7), ev("C", "Y", "C2", "c2", "AC2", 8),
    ])
    result = resolve_via_structural_equivalence(
        query_signature_id="Q", equivalence_state=state,
        signature_terminals={"B": "target-1", "C": "target-2"},
        known_signature_ids=["B", "C"],
    )
    assert result.resolved is False
    assert result.ambiguous is True
    assert result.source == "equivalence-conflict"
    assert result.equivalent_signature_ids == ("B", "C")


def test_multiple_supported_routes_to_same_terminal_can_converge():
    state = StructuralEquivalenceState()
    state.observe_many([
        ev("Q", "X", "Q1", "q1", "AB1", 1), ev("B", "X", "B1", "b1", "AB1", 2),
        ev("Q", "X", "Q2", "q2", "AB2", 3), ev("B", "X", "B2", "b2", "AB2", 4),
        ev("Q", "Y", "Q3", "q3", "AC1", 5), ev("C", "Y", "C1", "c1", "AC1", 6),
        ev("Q", "Y", "Q4", "q4", "AC2", 7), ev("C", "Y", "C2", "c2", "AC2", 8),
    ])
    result = resolve_via_structural_equivalence(
        query_signature_id="Q", equivalence_state=state,
        signature_terminals={"B": "target", "C": "target"},
        known_signature_ids=["C", "B"],
    )
    assert result.resolved is True
    assert result.terminal_region_id == "target"
    assert result.equivalent_signature_ids == ("B", "C")


def test_dense_hub_without_shared_witness_cannot_bridge():
    state = StructuralEquivalenceState()
    seq = 0
    for i in range(1000):
        seq += 1
        state.observe(ev("Q", "hub", f"Q{i}", f"q{i}", f"WQ{i}", seq))
        seq += 1
        state.observe(ev("B", "hub", f"B{i}", f"b{i}", f"WB{i}", seq))
    result = resolve_via_structural_equivalence(
        query_signature_id="Q", equivalence_state=state,
        signature_terminals={"B": "target"}, known_signature_ids=["B"]
    )
    assert result.resolved is False
    assert result.source == "unresolved"


def test_reconstructed_snapshot_produces_identical_resolution():
    state = supported_state()
    first = resolve_via_structural_equivalence(
        query_signature_id="Q", equivalence_state=state,
        signature_terminals={"B": "target"}, known_signature_ids=["B"]
    )
    restored = StructuralEquivalenceState(events=list(state.snapshot()))
    second = resolve_via_structural_equivalence(
        query_signature_id="Q", equivalence_state=restored,
        signature_terminals={"B": "target"}, known_signature_ids=["B"]
    )
    assert second == first
