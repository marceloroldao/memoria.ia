from memoria_resolutiva.live_infinita_adapter_v2 import make_live_request
from memoria_resolutiva.situated_live_gym_v2 import SituatedLiveCognitiveGymV2


INTERVENTION = "live:intervention:probe"


def _request(region: str, frame: str):
    state = ("live:entity:nova", f"live:region:{region}")
    candidate_x = (
        "x",
        ("live:effect:x",),
        ("live:entity:nova", f"live:region:{region}", "live:effect:x"),
    )
    candidate_y = (
        "y",
        ("live:effect:y",),
        ("live:entity:nova", f"live:region:{region}", "live:effect:y"),
    )
    return make_live_request(
        frame_id=frame,
        state_addresses=state,
        intervention_id=f"proposal:{frame}",
        intervention_address=INTERVENTION,
        candidates=(candidate_x, candidate_y),
    )


def _resolved_id(step):
    candidate = step.effective_prediction.resolved_candidate
    return None if candidate is None else candidate.candidate_id


def test_r1_x_r2_y_return_r1_x_uses_situated_regimes():
    gym = SituatedLiveCognitiveGymV2(
        min_independent_episodes=2,
        min_contiguous_support=2,
    )

    # R1 learns X historically and establishes local active continuity.
    r1_1 = gym.step(_request("r1", "r1-1"), actual_candidate_id="x")
    r1_2 = gym.step(_request("r1", "r1-2"), actual_candidate_id="x")
    assert r1_1.current_regime.active is None
    assert r1_2.current_regime.active is not None
    assert r1_2.current_regime.active.consequence_addresses == ("live:effect:x",)

    # With both X and Y offered by the world, the situated regime must narrow R1 to X.
    r1_probe = gym.step(_request("r1", "r1-probe"), actual_candidate_id="x", learn=False)
    assert r1_probe.base_prediction.ambiguous is True
    assert _resolved_id(r1_probe) == "x"

    # R2 is structurally isomorphic but begins with no local active regime.
    r2_1 = gym.step(_request("r2", "r2-1"), actual_candidate_id="y")
    assert r2_1.context_key.structural_key == r1_probe.context_key.structural_key
    assert r2_1.context_key != r1_probe.context_key
    assert r2_1.effective_prediction.ambiguous is True
    assert r2_1.current_regime.active is None

    # Persistent Y establishes a separate situated regime for R2.
    r2_2 = gym.step(_request("r2", "r2-2"), actual_candidate_id="y")
    assert r2_2.current_regime.active is not None
    assert r2_2.current_regime.active.consequence_addresses == ("live:effect:y",)

    r2_probe = gym.step(_request("r2", "r2-probe"), actual_candidate_id="y", learn=False)
    assert r2_probe.base_prediction.ambiguous is True
    assert _resolved_id(r2_probe) == "y"

    # Returning to R1 recovers the old local regime immediately; no relearning needed.
    back_r1 = gym.step(_request("r1", "r1-return"), actual_candidate_id="x", learn=False)
    assert back_r1.prior_regime.active is not None
    assert back_r1.prior_regime.active.consequence_addresses == ("live:effect:x",)
    assert _resolved_id(back_r1) == "x"


def test_r2_learning_does_not_replace_r1_active_regime():
    gym = SituatedLiveCognitiveGymV2(min_independent_episodes=2, min_contiguous_support=2)
    gym.step(_request("r1", "a1"), actual_candidate_id="x")
    gym.step(_request("r1", "a2"), actual_candidate_id="x")
    gym.step(_request("r2", "b1"), actual_candidate_id="y")
    gym.step(_request("r2", "b2"), actual_candidate_id="y")

    r1 = gym.step(_request("r1", "check-r1"), actual_candidate_id="x", learn=False)
    r2 = gym.step(_request("r2", "check-r2"), actual_candidate_id="y", learn=False)
    assert _resolved_id(r1) == "x"
    assert _resolved_id(r2) == "y"


def test_isomorphic_unknown_region_has_no_borrowed_active_regime():
    gym = SituatedLiveCognitiveGymV2(min_independent_episodes=2, min_contiguous_support=2)
    gym.step(_request("r1", "a1"), actual_candidate_id="x")
    gym.step(_request("r1", "a2"), actual_candidate_id="x")

    r3 = gym.step(_request("r3", "new"), actual_candidate_id="y", learn=False)
    assert r3.context_key.structural_key == gym.step(
        _request("r1", "probe"), actual_candidate_id="x", learn=False
    ).context_key.structural_key
    assert r3.prior_regime.active is None
    assert r3.effective_prediction.ambiguous is True
