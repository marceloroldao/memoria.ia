from memoria_resolutiva.address_trajectory_v2 import AddressTrajectory
from memoria_resolutiva.structural_equivalence_v2 import StructuralEquivalenceState
from memoria_resolutiva.structural_witness_discovery_v2 import (
    TrajectoryOccurrence,
    discover_witnesses,
    events_from_discovered_witnesses,
)


def traj(tid: str, *addresses: str) -> AddressTrajectory:
    return AddressTrajectory(tid, tid, tuple(addresses), tuple(addresses))


def test_independent_repeated_convergence_discovers_supported_equivalence():
    occ = (
        TrajectoryOccurrence(traj("T1", "a", "p", "q", "z"), "L1", "O1"),
        TrajectoryOccurrence(traj("T2", "b", "p", "q", "z"), "L2", "O2"),
        TrajectoryOccurrence(traj("T3", "a", "p", "q", "z"), "L3", "O3"),
        TrajectoryOccurrence(traj("T4", "b", "p", "q", "z"), "L4", "O4"),
    )
    witnesses = discover_witnesses(occ)
    state = StructuralEquivalenceState()
    state.observe_many(events_from_discovered_witnesses(witnesses))
    pairs = {(w.left_signature_id, w.right_signature_id) for w in witnesses}
    assert len(pairs) == 1
    left, right = next(iter(pairs))
    candidate = state.evaluate(left, right)
    assert candidate.state == "supported"
    assert candidate.independent_convergence >= 2


def test_shared_terminal_without_bridge_never_creates_witness():
    occ = tuple(
        TrajectoryOccurrence(traj(f"T{i}", f"src{i}", f"unique{i}", "hub"), f"L{i}", f"O{i}")
        for i in range(200)
    )
    assert discover_witnesses(occ) == ()


def test_one_shared_bridge_address_is_insufficient_by_default():
    occ = (
        TrajectoryOccurrence(traj("T1", "a", "bridge", "hub"), "L1", "O1"),
        TrajectoryOccurrence(traj("T2", "b", "bridge", "hub"), "L2", "O2"),
    )
    assert discover_witnesses(occ) == ()


def test_same_lineage_replay_cannot_create_witness():
    occ = tuple(
        TrajectoryOccurrence(traj(f"T{i}", "a" if i % 2 == 0 else "b", "p", "q", "z"), "same", f"O{i}")
        for i in range(100)
    )
    assert discover_witnesses(occ) == ()


def test_single_independent_pair_is_candidate_not_supported():
    occ = (
        TrajectoryOccurrence(traj("T1", "a", "p", "q", "z"), "L1", "O1"),
        TrajectoryOccurrence(traj("T2", "b", "p", "q", "z"), "L2", "O2"),
    )
    witnesses = discover_witnesses(occ)
    assert len(witnesses) == 1
    state = StructuralEquivalenceState()
    state.observe_many(events_from_discovered_witnesses(witnesses))
    candidate = state.evaluate(witnesses[0].left_signature_id, witnesses[0].right_signature_id)
    assert candidate.state == "candidate"


def test_multimodal_addresses_participate_without_text_semantics():
    occ = (
        TrajectoryOccurrence(traj("S1", "sensor:a", "joint:1", "joint:2", "future:x"), "sensor-L1", "sensor-O1"),
        TrajectoryOccurrence(traj("A1", "audio:b", "joint:1", "joint:2", "future:x"), "audio-L2", "audio-O2"),
    )
    witnesses = discover_witnesses(occ)
    assert len(witnesses) == 1
    assert witnesses[0].bridge_addresses == ("joint:1", "joint:2")


def test_no_transitive_closure_is_created():
    occ = (
        TrajectoryOccurrence(traj("T1", "a", "p", "q", "z"), "L1", "O1"),
        TrajectoryOccurrence(traj("T2", "b", "p", "q", "z"), "L2", "O2"),
        TrajectoryOccurrence(traj("T3", "b", "r", "s", "y"), "L3", "O3"),
        TrajectoryOccurrence(traj("T4", "c", "r", "s", "y"), "L4", "O4"),
    )
    witnesses = discover_witnesses(occ)
    assert len(witnesses) == 2
    # Detector emits only directly observed pairs; it never synthesizes A~C.
    direct_pairs = {(w.left_signature_id, w.right_signature_id) for w in witnesses}
    assert len(direct_pairs) == 2


def test_discovery_is_deterministic_under_input_order():
    occ = (
        TrajectoryOccurrence(traj("T1", "a", "p", "q", "z"), "L1", "O1"),
        TrajectoryOccurrence(traj("T2", "b", "p", "q", "z"), "L2", "O2"),
        TrajectoryOccurrence(traj("T3", "a", "p", "q", "z"), "L3", "O3"),
        TrajectoryOccurrence(traj("T4", "b", "p", "q", "z"), "L4", "O4"),
    )
    assert discover_witnesses(occ) == discover_witnesses(tuple(reversed(occ)))
