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


def _learned():
    occurrences = (
        occ("T1", "L1", "ta", "train:a", "train:b", "train:c", "train:future", "tx1"),
        occ("T2", "L2", "tb", "train:a", "train:b", "train:c", "train:future", "tx2"),
    )
    return (
        build_relation_profile(occurrences, ("train:a", "train:b", "train:c")),
        build_role_profile(occurrences, "train:future"),
    )


def _held_relation():
    occurrences = (
        occ("H1", "HL1", "ha", "held:a", "held:b", "held:c", "held:observed", "hx1"),
        occ("H2", "HL2", "hb", "held:a", "held:b", "held:c", "held:observed", "hx2"),
    )
    return occurrences, build_relation_profile(occurrences, ("held:a", "held:b", "held:c"))


def _candidate(prefix: str):
    # Match the learned future's anonymous local role: index 4 of a six-address
    # trajectory, with two independent lineages and one distinct successor per
    # predecessor. Literal addresses remain disjoint.
    occurrences = (
        occ(
            prefix + "1",
            prefix + "L1",
            prefix + "p0",
            prefix + "p1",
            prefix + "p2",
            prefix + "p3",
            prefix + ":future",
            prefix + "s1",
        ),
        occ(
            prefix + "2",
            prefix + "L2",
            prefix + "q0",
            prefix + "q1",
            prefix + "q2",
            prefix + "q3",
            prefix + ":future",
            prefix + "s2",
        ),
    )
    return StructuralFutureCandidate(prefix + ":candidate", build_role_profile(occurrences, prefix + ":future"))


def test_disjoint_heldout_space_can_select_unique_future_by_structural_role():
    learned_relation, learned_future = _learned()
    _, held_relation = _held_relation()
    good = _candidate("good")
    bad_occ = (
        occ("B1", "BL1", "bp1", "bad:future", "bs1"),
        occ("B2", "BL2", "bp2", "bad:future", "bs2"),
    )
    bad = StructuralFutureCandidate("bad:candidate", build_role_profile(bad_occ, "bad:future"))

    result = forecast_structural_future(
        learned_relation=learned_relation,
        heldout_relation=held_relation,
        learned_future_role=learned_future,
        heldout_candidates=(bad, good),
    )
    assert result.resolved is True
    assert result.candidate_id == "good:candidate"
    assert result.source == "structural-transfer"


def test_two_equally_compatible_future_roles_remain_ambiguous():
    learned_relation, learned_future = _learned()
    _, held_relation = _held_relation()
    result = forecast_structural_future(
        learned_relation=learned_relation,
        heldout_relation=held_relation,
        learned_future_role=learned_future,
        heldout_candidates=(_candidate("x"), _candidate("y")),
    )
    assert result.resolved is False
    assert result.ambiguous is True
    assert result.competing_candidate_ids == ("x:candidate", "y:candidate")


def test_relation_mismatch_blocks_future_transfer_even_when_candidate_role_matches():
    learned_relation, learned_future = _learned()
    mismatch_occ = (
        occ("M1", "ML1", "ma", "held:a", "held:b", "held:c", "mx1", "mx2", "mx3"),
        occ("M2", "ML2", "mb", "held:a", "held:b", "held:c", "my1", "my2", "my3"),
    )
    mismatch_relation = build_relation_profile(mismatch_occ, ("held:a", "held:b", "held:c"))
    result = forecast_structural_future(
        learned_relation=learned_relation,
        heldout_relation=mismatch_relation,
        learned_future_role=learned_future,
        heldout_candidates=(_candidate("good"),),
    )
    assert result.resolved is False
    assert result.source == "relation-not-transferable"


def test_no_compatible_future_role_stays_unresolved():
    learned_relation, learned_future = _learned()
    _, held_relation = _held_relation()
    bad_occ = (
        occ("B1", "BL1", "bp1", "bad:future", "bs1"),
        occ("B2", "BL2", "bp2", "bad:future", "bs2"),
    )
    result = forecast_structural_future(
        learned_relation=learned_relation,
        heldout_relation=held_relation,
        learned_future_role=learned_future,
        heldout_candidates=(StructuralFutureCandidate("bad", build_role_profile(bad_occ, "bad:future")),),
    )
    assert result.resolved is False
    assert result.ambiguous is False
    assert result.source == "no-compatible-future-role"
