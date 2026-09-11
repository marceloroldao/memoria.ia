from memoria_resolutiva.active_information_v2 import derive_active_information_intent
from memoria_resolutiva.dynamic_branch_state_v2 import BranchHypothesis, BranchState
from memoria_resolutiva.structural_curiosity_v2 import derive_curiosity


def _state(*paths):
    branches = tuple(
        BranchHypothesis(
            trajectory_ids=(f"T{i}",),
            remaining_addresses=tuple(path),
        )
        for i, path in enumerate(paths, start=1)
    )
    return BranchState(active=branches, eliminated=(), observation_history=())


def test_shared_future_is_not_mistaken_for_information_target():
    probe = derive_curiosity(_state(("c", "d"), ("c", "omega")))
    intent = derive_active_information_intent(probe)
    assert intent.active is True
    assert intent.target_depth == 1
    assert intent.accepted_observations == ("d", "omega")
    assert "c" not in intent.accepted_observations


def test_single_branch_does_not_create_artificial_information_need():
    intent = derive_active_information_intent(derive_curiosity(_state(("c", "d"))))
    assert intent.active is False
    assert intent.mode == "none"


def test_identical_branches_do_not_create_artificial_information_need():
    intent = derive_active_information_intent(
        derive_curiosity(_state(("c", "d"), ("c", "d")))
    )
    assert intent.active is False


def test_terminal_branch_is_a_real_discriminative_outcome():
    intent = derive_active_information_intent(
        derive_curiosity(_state(("c",), ("c", "d")))
    )
    assert intent.active is True
    assert intent.target_depth == 1
    assert intent.accepted_observations == ("d", "<END>")


def test_active_information_is_deterministic_under_branch_order():
    a = derive_active_information_intent(
        derive_curiosity(_state(("c", "omega"), ("c", "d")))
    )
    b = derive_active_information_intent(
        derive_curiosity(_state(("c", "d"), ("c", "omega")))
    )
    assert a.target_depth == b.target_depth
    assert a.accepted_observations == b.accepted_observations
