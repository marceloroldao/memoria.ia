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


def _relation_and_future(prefix: str, *, divergent: bool = False):
    if divergent:
        occurrences = (
            occ(prefix + "1", prefix + "L1", prefix + "pre", prefix + ":a", prefix + ":b", prefix + ":c", prefix + ":future", prefix + ":s1"),
            occ(prefix + "2", prefix + "L2", prefix + "pre", prefix + ":a", prefix + ":b", prefix + ":c", prefix + ":future", prefix + ":s2", prefix + ":tail"),
        )
    else:
        occurrences = (
            occ(prefix + "1", prefix + "L1", prefix + "pre", prefix + ":a", prefix + ":b", prefix + ":c", prefix + ":future", prefix + ":s1"),
            occ(prefix + "2", prefix + "L2", prefix + "pre", prefix + ":a", prefix + ":b", prefix + ":c", prefix + ":future", prefix + ":s2"),
        )
    relation = build_relation_profile(occurrences, (prefix + ":a", prefix + ":b", prefix + ":c"))
    future = build_role_profile(occurrences, prefix + ":future")
    return occurrences, relation, future


def test_identical_local_future_roles_are_disambiguated_only_by_relational_context():
    _, learned_relation, learned_future = _relation_and_future("train")
    _, heldout_relation, _ = _relation_and_future("held")
    _, good_context, good_role = _relation_and_future("good")

    # The lookalike future is constructed with the same local role as the good
    # candidate, but its relation has a different deeper continuation regime.
    bad_role_occurrences = (
        occ("badR1", "badRL1", "bad:pre", "bad:r1", "bad:r2", "bad:r3", "bad:future", "bad:s1"),
        occ("badR2", "badRL2", "bad:pre", "bad:r1", "bad:r2", "bad:r3", "bad:future", "bad:s2"),
    )
    bad_role = build_role_profile(bad_role_occurrences, "bad:future")
    _, bad_context, _ = _relation_and_future("badctx", divergent=True)

    assert good_role.role_id == bad_role.role_id
    assert good_context.relation_id == heldout_relation.relation_id
    assert bad_context.relation_id != heldout_relation.relation_id

    result = forecast_structural_future(
        learned_relation=learned_relation,
        heldout_relation=heldout_relation,
        learned_future_role=learned_future,
        heldout_candidates=(
            StructuralFutureCandidate("bad", bad_role, bad_context),
            StructuralFutureCandidate("good", good_role, good_context),
        ),
    )

    assert result.resolved is True
    assert result.candidate_id == "good"
    assert result.source == "structural-transfer-context"
    assert result.ambiguous is False


def test_contextual_tie_remains_ambiguous():
    _, learned_relation, learned_future = _relation_and_future("train2")
    _, heldout_relation, _ = _relation_and_future("held2")
    _, context_a, role_a = _relation_and_future("a")
    _, context_b, role_b = _relation_and_future("b")

    result = forecast_structural_future(
        learned_relation=learned_relation,
        heldout_relation=heldout_relation,
        learned_future_role=learned_future,
        heldout_candidates=(
            StructuralFutureCandidate("a", role_a, context_a),
            StructuralFutureCandidate("b", role_b, context_b),
        ),
    )

    assert result.resolved is False
    assert result.ambiguous is True
    assert result.competing_candidate_ids == ("a", "b")
