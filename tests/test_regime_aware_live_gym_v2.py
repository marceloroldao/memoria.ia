from memoria_resolutiva.live_infinita_adapter_v2 import make_live_request
from memoria_resolutiva.regime_aware_live_gym_v2 import RegimeAwareLiveCognitiveGymV2


def _request(index: int):
    return make_live_request(
        frame_id=f"F{index}",
        state_addresses=("world:anchor", "world:zone"),
        intervention_id=f"I{index}",
        intervention_address="action:step",
        candidates=(
            ("a", ("effect:a",), ("world:anchor", "effect:a")),
            ("b", ("effect:b",), ("world:anchor", "effect:b")),
        ),
        provenance="regime-aware-live-gym-v2",
    )


def test_regime_resolves_structural_ambiguity_after_contiguous_support():
    gym = RegimeAwareLiveCognitiveGymV2(min_contiguous_support=2)
    gym.step(_request(0), actual_candidate_id="a", learn=True)
    gym.step(_request(1), actual_candidate_id="a", learn=True)
    step = gym.step(_request(2), actual_candidate_id="a", learn=True)
    assert step.base_prediction.ambiguous is True
    assert step.effective_prediction.resolved is True
    assert step.effective_prediction.resolved_candidate.candidate_id == "a"
    assert step.error.kind == "prediction-confirmed"


def test_regime_switch_produces_surprise_then_adapts_without_erasing_history():
    gym = RegimeAwareLiveCognitiveGymV2(min_contiguous_support=2)
    for index in range(4):
        gym.step(_request(index), actual_candidate_id="a", learn=True)

    first_b = gym.step(_request(4), actual_candidate_id="b", learn=True)
    assert first_b.effective_prediction.resolved_candidate.candidate_id == "a"
    assert first_b.error.kind == "total-surprise"
    assert first_b.attention.level == "reorient"
    assert first_b.regime_update.current.active_key == "a"

    second_b = gym.step(_request(5), actual_candidate_id="b", learn=True)
    assert second_b.error.kind == "total-surprise"
    assert second_b.regime_update.switched is True
    assert second_b.regime_update.current.active_key == "b"

    third_b = gym.step(_request(6), actual_candidate_id="b", learn=True)
    assert third_b.effective_prediction.resolved_candidate.candidate_id == "b"
    assert third_b.error.kind == "prediction-confirmed"

    # Persistent memory still contains both historical outcomes.
    historical = gym.base.memory.resolve(
        ("world:anchor", "world:zone"),
        "action:step",
        min_independent_episodes=2,
    )
    assert historical.ambiguous is True
    assert len(historical.hypotheses) == 2


def test_regime_state_can_be_restored_deterministically():
    gym = RegimeAwareLiveCognitiveGymV2(min_contiguous_support=2)
    for index in range(3):
        gym.step(_request(index), actual_candidate_id="a", learn=True)

    restored = RegimeAwareLiveCognitiveGymV2(
        memory=gym.memory.restore(gym.memory.snapshot()),
        min_contiguous_support=2,
        regime=gym.regime,
    )
    a = gym.step(_request(10), actual_candidate_id="a", learn=False)
    b = restored.step(_request(10), actual_candidate_id="a", learn=False)
    assert a.effective_prediction.reason == b.effective_prediction.reason
    assert a.effective_prediction.resolved_candidate == b.effective_prediction.resolved_candidate
    assert a.error == b.error
    assert a.regime_update.current == b.regime_update.current
