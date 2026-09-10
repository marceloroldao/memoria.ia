from memoria_resolutiva.address_trajectory_v2 import AddressTrajectory
from memoria_resolutiva.structural_relation_abstraction_v2 import build_relation_profile, compare_structural_relations
from memoria_resolutiva.structural_witness_discovery_v2 import TrajectoryOccurrence


def traj(tid: str, *addresses: str) -> AddressTrajectory:
    return AddressTrajectory(tid, tid, tuple(addresses), tuple(addresses))


def _occ(prefix: str, left: str, bridge: str, right: str):
    return (
        TrajectoryOccurrence(traj(prefix + "1", prefix + "a", left, bridge, right, prefix + "tail1"), prefix + "L1", prefix + "O1"),
        TrajectoryOccurrence(traj(prefix + "2", prefix + "b", left, bridge, right, prefix + "tail2"), prefix + "L2", prefix + "O2"),
    )


def test_disjoint_spaces_can_match_ordered_three_node_relation():
    train = _occ("T", "train:left", "train:bridge", "train:right")
    held = _occ("H", "held:left", "held:bridge", "held:right")
    assert {a for o in train for a in o.trajectory.addresses}.isdisjoint(
        {a for o in held for a in o.trajectory.addresses}
    )
    left = build_relation_profile(train, ("train:left", "train:bridge", "train:right"))
    right = build_relation_profile(held, ("held:left", "held:bridge", "held:right"))
    match = compare_structural_relations(left, right)
    assert match.supported is True
    assert match.reason == "exact-structural-relation"


def test_permuted_order_does_not_match_relation():
    train = _occ("T", "train:left", "train:bridge", "train:right")
    held = (
        TrajectoryOccurrence(traj("H1", "Ha", "held:right", "held:bridge", "held:left", "Ht1"), "HL1", "HO1"),
        TrajectoryOccurrence(traj("H2", "Hb", "held:right", "held:bridge", "held:left", "Ht2"), "HL2", "HO2"),
    )
    left = build_relation_profile(train, ("train:left", "train:bridge", "train:right"))
    right = build_relation_profile(held, ("held:left", "held:bridge", "held:right"))
    assert compare_structural_relations(left, right).supported is False


def test_relation_requires_independent_support_on_both_spaces():
    train = _occ("T", "train:left", "train:bridge", "train:right")
    held = (
        TrajectoryOccurrence(traj("H1", "Ha", "held:left", "held:bridge", "held:right", "Ht1"), "same", "HO1"),
        TrajectoryOccurrence(traj("H2", "Hb", "held:left", "held:bridge", "held:right", "Ht2"), "same", "HO2"),
    )
    left = build_relation_profile(train, ("train:left", "train:bridge", "train:right"))
    right = build_relation_profile(held, ("held:left", "held:bridge", "held:right"))
    result = compare_structural_relations(left, right)
    assert result.supported is False
    assert result.reason == "insufficient-independent-support"


def test_same_local_relation_but_different_deeper_future_regime_is_blocked():
    # Immediate continuation has one address on both sides. Divergence appears one
    # step later. A purely local relation fingerprint would alias these motifs.
    left_occ = (
        TrajectoryOccurrence(traj("L1", "a1", "l1", "l2", "l3", "sharedL", "endL"), "LL1", "LO1"),
        TrajectoryOccurrence(traj("L2", "a2", "l1", "l2", "l3", "sharedL", "endL"), "LL2", "LO2"),
    )
    right_occ = (
        TrajectoryOccurrence(traj("R1", "b1", "r1", "r2", "r3", "sharedR", "endR1"), "RL1", "RO1"),
        TrajectoryOccurrence(traj("R2", "b2", "r1", "r2", "r3", "sharedR", "endR2"), "RL2", "RO2"),
    )
    left = build_relation_profile(left_occ, ("l1", "l2", "l3"), max_continuation_depth=2)
    right = build_relation_profile(right_occ, ("r1", "r2", "r3"), max_continuation_depth=2)
    assert left.continuation_diversity_by_depth == (1, 1)
    assert right.continuation_diversity_by_depth == (1, 2)
    result = compare_structural_relations(left, right)
    assert result.supported is False
    assert result.reason == "relation-topology-mismatch"


def test_duplicate_replays_do_not_replace_independent_lineages():
    left_occ = (
        TrajectoryOccurrence(traj("L1", "a", "l1", "l2", "l3", "x"), "same", "LO1"),
        TrajectoryOccurrence(traj("L2", "b", "l1", "l2", "l3", "x"), "same", "LO2"),
        TrajectoryOccurrence(traj("L3", "c", "l1", "l2", "l3", "x"), "same", "LO3"),
    )
    right_occ = _occ("R", "r1", "r2", "r3")
    left = build_relation_profile(left_occ, ("l1", "l2", "l3"))
    right = build_relation_profile(right_occ, ("r1", "r2", "r3"))
    assert left.independent_lineages == 1
    assert compare_structural_relations(left, right).supported is False


def test_relation_profile_is_read_only_and_deterministic():
    occ = _occ("T", "a", "b", "c")
    before = tuple(occ)
    first = build_relation_profile(occ, ("a", "b", "c"))
    second = build_relation_profile(tuple(reversed(occ)), ("a", "b", "c"))
    assert first.relation_id == second.relation_id
    assert tuple(occ) == before
