from memoria_resolutiva.address_trajectory_v2 import AddressTrajectory
from memoria_resolutiva.structural_role_abstraction_v2 import build_role_profile, compare_structural_roles
from memoria_resolutiva.structural_witness_discovery_v2 import TrajectoryOccurrence


def traj(tid: str, *addresses: str) -> AddressTrajectory:
    return AddressTrajectory(tid, tid, tuple(addresses), tuple(addresses))


def _occ(prefix: str, left: str, bridge: str, right: str, tail: str):
    return (
        TrajectoryOccurrence(traj(prefix + "1", prefix + "a", left, bridge, right, tail + "1"), prefix + "L1", prefix + "O1"),
        TrajectoryOccurrence(traj(prefix + "2", prefix + "b", left, bridge, right, tail + "2"), prefix + "L2", prefix + "O2"),
    )


def test_disjoint_spaces_can_match_a_three_node_structural_relation_role_by_role():
    train = _occ("T", "train:left", "train:bridge", "train:right", "train:tail")
    held = _occ("H", "held:left", "held:bridge", "held:right", "held:tail")
    train_addresses = {a for o in train for a in o.trajectory.addresses}
    held_addresses = {a for o in held for a in o.trajectory.addresses}
    assert train_addresses.isdisjoint(held_addresses)

    for left, right in (
        ("train:left", "held:left"),
        ("train:bridge", "held:bridge"),
        ("train:right", "held:right"),
    ):
        match = compare_structural_roles(build_role_profile(train, left), build_role_profile(held, right))
        assert match.supported is True


def test_same_individual_roles_do_not_prove_same_relation_when_order_is_permuted():
    train = _occ("T", "train:left", "train:bridge", "train:right", "train:tail")
    # Same local ingredients are deliberately permuted in the held-out relation.
    held = (
        TrajectoryOccurrence(traj("H1", "Ha", "held:right", "held:bridge", "held:left", "Ht1"), "HL1", "HO1"),
        TrajectoryOccurrence(traj("H2", "Hb", "held:right", "held:bridge", "held:left", "Ht2"), "HL2", "HO2"),
    )

    # A relation-level abstraction must eventually reject this even if some local
    # roles collide. This assertion records the current architectural gap instead
    # of teaching semantic labels or adding a lexical shortcut.
    left_match = compare_structural_roles(
        build_role_profile(train, "train:left"), build_role_profile(held, "held:left")
    )
    right_match = compare_structural_roles(
        build_role_profile(train, "train:right"), build_role_profile(held, "held:right")
    )
    assert not (left_match.supported and right_match.supported)


def test_relation_transfer_requires_independent_support_on_both_spaces():
    train = _occ("T", "train:left", "train:bridge", "train:right", "train:tail")
    held = (
        TrajectoryOccurrence(traj("H1", "Ha", "held:left", "held:bridge", "held:right", "Ht1"), "same", "HO1"),
        TrajectoryOccurrence(traj("H2", "Hb", "held:left", "held:bridge", "held:right", "Ht2"), "same", "HO2"),
    )
    assert compare_structural_roles(
        build_role_profile(train, "train:bridge"), build_role_profile(held, "held:bridge")
    ).supported is False
