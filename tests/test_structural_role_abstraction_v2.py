from memoria_resolutiva.address_trajectory_v2 import AddressTrajectory
from memoria_resolutiva.structural_role_abstraction_v2 import build_role_profile, compare_structural_roles
from memoria_resolutiva.structural_witness_discovery_v2 import TrajectoryOccurrence


def traj(tid: str, *addresses: str) -> AddressTrajectory:
    return AddressTrajectory(tid, tid, tuple(addresses), tuple(addresses))


def test_disjoint_address_spaces_can_share_exact_topological_role():
    train = (
        TrajectoryOccurrence(traj("T1", "ta", "focus:train", "tb", "tc"), "TL1", "TO1"),
        TrajectoryOccurrence(traj("T2", "td", "focus:train", "te", "tf"), "TL2", "TO2"),
    )
    heldout = (
        TrajectoryOccurrence(traj("H1", "ha", "focus:heldout", "hb", "hc"), "HL1", "HO1"),
        TrajectoryOccurrence(traj("H2", "hd", "focus:heldout", "he", "hf"), "HL2", "HO2"),
    )
    train_addresses = {a for o in train for a in o.trajectory.addresses}
    heldout_addresses = {a for o in heldout for a in o.trajectory.addresses}
    assert train_addresses.isdisjoint(heldout_addresses)
    left = build_role_profile(train, "focus:train")
    right = build_role_profile(heldout, "focus:heldout")
    match = compare_structural_roles(left, right)
    assert match.supported is True
    assert match.reason == "exact-topological-role"


def test_partial_shape_similarity_does_not_transfer():
    left_occ = (
        TrajectoryOccurrence(traj("T1", "a", "focus:left", "b", "c"), "L1", "O1"),
        TrajectoryOccurrence(traj("T2", "d", "focus:left", "e", "f"), "L2", "O2"),
    )
    right_occ = (
        TrajectoryOccurrence(traj("R1", "x", "focus:right", "y"), "R1", "RO1"),
        TrajectoryOccurrence(traj("R2", "z", "focus:right", "w"), "R2", "RO2"),
    )
    match = compare_structural_roles(
        build_role_profile(left_occ, "focus:left"),
        build_role_profile(right_occ, "focus:right"),
    )
    assert match.supported is False
    assert match.reason == "topology-mismatch"


def test_single_lineage_cannot_establish_transferable_role():
    left_occ = (
        TrajectoryOccurrence(traj("T1", "a", "focus:left", "b", "c"), "same", "O1"),
        TrajectoryOccurrence(traj("T2", "d", "focus:left", "e", "f"), "same", "O2"),
    )
    right_occ = (
        TrajectoryOccurrence(traj("R1", "x", "focus:right", "y", "z"), "same2", "RO1"),
        TrajectoryOccurrence(traj("R2", "u", "focus:right", "v", "w"), "same2", "RO2"),
    )
    match = compare_structural_roles(
        build_role_profile(left_occ, "focus:left"),
        build_role_profile(right_occ, "focus:right"),
    )
    assert match.supported is False
    assert match.reason == "insufficient-independent-support"


def test_hyperdense_role_fails_closed():
    left_occ = tuple(
        TrajectoryOccurrence(traj(f"T{i}", f"p{i}", "focus:left", f"s{i}", f"t{i}"), f"L{i}", f"O{i}")
        for i in range(64)
    )
    right_occ = tuple(
        TrajectoryOccurrence(traj(f"R{i}", f"q{i}", "focus:right", f"u{i}", f"v{i}"), f"RL{i}", f"RO{i}")
        for i in range(64)
    )
    left = build_role_profile(left_occ, "focus:left", max_neighbor_diversity=32)
    right = build_role_profile(right_occ, "focus:right", max_neighbor_diversity=32)
    assert left.discriminative is False
    assert right.discriminative is False
    assert compare_structural_roles(left, right).reason == "non-discriminative"


def test_role_comparison_is_read_only_and_deterministic():
    occ = (
        TrajectoryOccurrence(traj("T1", "a", "focus", "b", "c"), "L1", "O1"),
        TrajectoryOccurrence(traj("T2", "d", "focus", "e", "f"), "L2", "O2"),
    )
    before = tuple(occ)
    first = build_role_profile(occ, "focus")
    second = build_role_profile(tuple(reversed(occ)), "focus")
    assert first.role_id == second.role_id
    assert tuple(occ) == before
