from memoria_resolutiva.address_trajectory_v2 import AddressTrajectory
from memoria_resolutiva.structural_relation_abstraction_v2 import build_relation_profile
from memoria_resolutiva.structural_role_abstraction_v2 import build_role_profile
from memoria_resolutiva.structural_transfer_forecast_v2 import (
    StructuralFutureCandidate,
    forecast_structural_future,
)
from memoria_resolutiva.structural_witness_discovery_v2 import TrajectoryOccurrence


def traj(tid: str, *addresses: str) -> AddressTrajectory:
    return AddressTrajectory(tid, tid, tuple(addresses), tuple(addresses))


def occ(tid: str, lineage: str, *addresses: str) -> TrajectoryOccurrence:
    return TrajectoryOccurrence(traj(tid, *addresses), lineage, tid + ":occ")


def learned_fixture():
    occurrences = (
        occ("T1", "L1", "ta", "train:a", "train:b", "train:c", "train:future", "tx1"),
        occ("T2", "L2", "tb", "train:a", "train:b", "train:c", "train:future", "tx2"),
    )
    return (
        build_relation_profile(occurrences, ("train:a", "train:b", "train:c")),
        build_role_profile(occurrences, "train:future"),
    )


def held_fixture():
    occurrences = (
        occ("H1", "HL1", "ha", "held:a", "held:b", "held:c", "held:future", "hx1"),
        occ("H2", "HL2", "hb", "held:a", "held:b", "held:c", "held:future", "hx2"),
    )
    return occurrences, build_relation_profile(occurrences, ("held:a", "held:b", "held:c"))


def candidate_from_context(prefix: str, relation: tuple[str, str, str], *, shared_predecessor: bool = True):
    p1 = relation
    p2 = relation if shared_predecessor else (relation[0] + "2", relation[1] + "2", relation[2] + "2")
    occurrences = (
        occ(prefix + "1", prefix + "L1", prefix + "p0", *p1, prefix + ":future", prefix + "s1"),
        occ(prefix + "2", prefix + "L2", prefix + "q0", *p2, prefix + ":future", prefix + "s2"),
    )
    return StructuralFutureCandidate(
        prefix + ":candidate",
        build_role_profile(occurrences, prefix + ":future"),
        occurrences=occurrences,
        focus_address=prefix + ":future",
    )


def test_context_is_derived_from_candidate_trajectory_without_manual_relation():
    learned_relation, learned_future = learned_fixture()
    _, held_relation = held_fixture()
    good = candidate_from_context("good", ("ctx:a", "ctx:b", "ctx:c"))

    # Give the candidate's context the same anonymous topology as the held relation.
    # Literal addresses remain disjoint from held:* and train:*.
    good_context_occ = good.occurrences
    good_context = build_relation_profile(good_context_occ, ("ctx:a", "ctx:b", "ctx:c"))
    assert good_context.relation_id == held_relation.relation_id

    result = forecast_structural_future(
        learned_relation=learned_relation,
        heldout_relation=held_relation,
        learned_future_role=learned_future,
        heldout_candidates=(good,),
    )
    assert result.resolved is True
    assert result.candidate_id == "good:candidate"
    assert result.source == "structural-transfer-context"


def test_local_role_lookalike_in_wrong_relation_is_rejected_automatically():
    learned_relation, learned_future = learned_fixture()
    _, held_relation = held_fixture()

    good = candidate_from_context("good", ("good:a", "good:b", "good:c"))
    wrong_occ = (
        occ("W1", "WL1", "wp0", "wrong:a", "wrong:b", "wrong:c", "wrong:future", "wx1", "tail"),
        occ("W2", "WL2", "wq0", "wrong:a", "wrong:b", "wrong:c", "wrong:future", "wx2", "tail"),
    )
    wrong = StructuralFutureCandidate(
        "wrong:candidate",
        build_role_profile(wrong_occ, "wrong:future"),
        occurrences=wrong_occ,
        focus_address="wrong:future",
    )

    # Both candidates intentionally share the learned future's local role geometry.
    assert good.role_profile.role_id == learned_future.role_id
    assert wrong.role_profile.role_id == learned_future.role_id

    result = forecast_structural_future(
        learned_relation=learned_relation,
        heldout_relation=held_relation,
        learned_future_role=learned_future,
        heldout_candidates=(wrong, good),
    )
    assert result.resolved is True
    assert result.candidate_id == "good:candidate"
    assert result.source == "structural-transfer-context"


def test_two_matching_derived_contexts_remain_ambiguous():
    learned_relation, learned_future = learned_fixture()
    _, held_relation = held_fixture()
    left = candidate_from_context("left", ("left:a", "left:b", "left:c"))
    right = candidate_from_context("right", ("right:a", "right:b", "right:c"))

    result = forecast_structural_future(
        learned_relation=learned_relation,
        heldout_relation=held_relation,
        learned_future_role=learned_future,
        heldout_candidates=(left, right),
    )
    assert result.resolved is False
    assert result.ambiguous is True
    assert result.competing_candidate_ids == ("left:candidate", "right:candidate")


def test_single_lineage_context_is_missing_evidence_not_false_confirmation():
    learned_relation, learned_future = learned_fixture()
    _, held_relation = held_fixture()
    occurrences = (
        occ("S1", "ONLY", "sp0", "solo:a", "solo:b", "solo:c", "solo:future", "sx1"),
        occ("S2", "ONLY", "sq0", "solo:a", "solo:b", "solo:c", "solo:future", "sx2"),
    )
    candidate = StructuralFutureCandidate(
        "solo:candidate",
        build_role_profile(occurrences, "solo:future"),
        occurrences=occurrences,
        focus_address="solo:future",
    )

    result = forecast_structural_future(
        learned_relation=learned_relation,
        heldout_relation=held_relation,
        learned_future_role=learned_future,
        heldout_candidates=(candidate,),
    )
    # The candidate role itself also lacks independent support, so it cannot resolve.
    assert result.resolved is False
    assert result.source == "no-compatible-future-role"
