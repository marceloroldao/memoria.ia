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


def test_equal_counts_and_positions_but_different_incidence_geometry_do_not_transfer():
    # Both sides have the same trajectory length, focus position, two predecessors
    # and two successors. Left is a one-to-one matching; right is crossed/all-to-all.
    # A count-only role fingerprint would collide here.
    left_occ = (
        TrajectoryOccurrence(traj("L1", "p1", "focus:left", "s1", "tail1"), "LL1", "LO1"),
        TrajectoryOccurrence(traj("L2", "p2", "focus:left", "s2", "tail2"), "LL2", "LO2"),
    )
    right_occ = (
        TrajectoryOccurrence(traj("R1", "q1", "focus:right", "u1", "end1"), "RL1", "RO1"),
        TrajectoryOccurrence(traj("R2", "q1", "focus:right", "u2", "end2"), "RL2", "RO2"),
        TrajectoryOccurrence(traj("R3", "q2", "focus:right", "u1", "end3"), "RL3", "RO3"),
        TrajectoryOccurrence(traj("R4", "q2", "focus:right", "u2", "end4"), "RL4", "RO4"),
    )
    left = build_role_profile(left_occ, "focus:left")
    right = build_role_profile(right_occ, "focus:right")
    assert left.predecessor_diversity == right.predecessor_diversity == 2
    assert left.successor_diversity == right.successor_diversity == 2
    assert left.local_shapes == right.local_shapes
    match = compare_structural_roles(left, right)
    assert match.supported is False
    assert match.reason == "topology-mismatch"


def test_same_degree_spectra_but_different_independent_support_do_not_transfer():
    # Neighbor coupling is the same shape, but one side is independently reinforced
    # per incidence while the other is replay-heavy. The support spectrum must differ.
    left_occ = (
        TrajectoryOccurrence(traj("L1", "p1", "focus:left", "s1", "t1"), "L1", "O1"),
        TrajectoryOccurrence(traj("L2", "p1", "focus:left", "s1", "t2"), "L2", "O2"),
        TrajectoryOccurrence(traj("L3", "p2", "focus:left", "s2", "t3"), "L3", "O3"),
        TrajectoryOccurrence(traj("L4", "p2", "focus:left", "s2", "t4"), "L4", "O4"),
    )
    right_occ = (
        TrajectoryOccurrence(traj("R1", "q1", "focus:right", "u1", "v1"), "sameA", "RO1"),
        TrajectoryOccurrence(traj("R2", "q1", "focus:right", "u1", "v2"), "sameA", "RO2"),
        TrajectoryOccurrence(traj("R3", "q2", "focus:right", "u2", "v3"), "sameB", "RO3"),
        TrajectoryOccurrence(traj("R4", "q2", "focus:right", "u2", "v4"), "sameB", "RO4"),
    )
    left = build_role_profile(left_occ, "focus:left")
    right = build_role_profile(right_occ, "focus:right")
    assert left.predecessor_degree_spectrum == right.predecessor_degree_spectrum
    assert left.successor_degree_spectrum == right.successor_degree_spectrum
    assert left.incidence_support_spectrum != right.incidence_support_spectrum
    assert compare_structural_roles(left, right).supported is False


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
