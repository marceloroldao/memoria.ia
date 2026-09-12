from memoria_resolutiva.contextual_live_gym_v2 import ContextualLiveCognitiveGymV2
from memoria_resolutiva.contextual_temporal_regime_v2 import contextual_regime_key
from memoria_resolutiva.live_infinita_adapter_v2 import make_live_request


def _request(frame: str, state, intervention, candidates):
    return make_live_request(
        frame_id=frame,
        state_addresses=state,
        intervention_id=f"I:{frame}",
        intervention_address=intervention,
        candidates=candidates,
        provenance="contextual-live-gym-v2",
    )


def test_distinct_structural_contexts_keep_independent_effective_predictions():
    gym = ContextualLiveCognitiveGymV2(min_contiguous_support=2)

    c1 = _request(
        "c1",
        ("r1", "anchor1"),
        "act:new",
        (
            ("a", ("effect:a",), ("r1", "effect:a")),
            ("x", ("effect:x",), ("r1", "effect:x")),
        ),
    )
    c2 = _request(
        "c2",
        ("r2", "r2"),
        "act:new",
        (
            ("b", ("effect:b",), ("r2", "effect:b")),
            ("y", ("effect:y",), ("r2", "effect:y")),
        ),
    )

    for i in range(3):
        gym.step(c1, actual_candidate_id="a", learn=True)
        gym.step(c2, actual_candidate_id="b", learn=True)

    s1 = gym.step(c1, actual_candidate_id="a", learn=False)
    s2 = gym.step(c2, actual_candidate_id="b", learn=False)
    assert s1.context_key != s2.context_key
    assert s1.current_regime.active.consequence_addresses == ("effect:a",)
    assert s2.current_regime.active.consequence_addresses == ("effect:b",)
    assert s1.effective_prediction.resolved_candidate.candidate_id == "a"
    assert s2.effective_prediction.resolved_candidate.candidate_id == "b"


def test_switching_context_and_returning_restores_local_continuity():
    gym = ContextualLiveCognitiveGymV2(min_contiguous_support=2)
    c1 = _request(
        "c1",
        ("x", "y"),
        "act:new",
        (("a", ("ea",), ("x", "ea")), ("b", ("eb",), ("x", "eb"))),
    )
    c2 = _request(
        "c2",
        ("z", "z"),
        "act:new",
        (("c", ("ec",), ("z", "ec")), ("d", ("ed",), ("z", "ed"))),
    )

    gym.step(c1, actual_candidate_id="a")
    gym.step(c1, actual_candidate_id="a")
    key1 = contextual_regime_key(c1.state.state_addresses, c1.intervention.address)
    before = gym.regimes.get(key1)

    gym.step(c2, actual_candidate_id="c")
    gym.step(c2, actual_candidate_id="c")
    assert gym.regimes.get(key1) == before

    returned = gym.step(c1, actual_candidate_id="a", learn=False)
    assert returned.prior_regime == before
    assert returned.current_regime.active.consequence_addresses == ("ea",)


def test_noise_in_one_context_does_not_reorient_another_context():
    gym = ContextualLiveCognitiveGymV2(min_contiguous_support=2)
    c1 = _request(
        "c1",
        ("x", "y"),
        "act:new",
        (("a", ("ea",), ("x", "ea")), ("noise", ("en",), ("x", "en"))),
    )
    c2 = _request(
        "c2",
        ("q", "q"),
        "act:new",
        (("b", ("eb",), ("q", "eb")), ("other", ("eo",), ("q", "eo"))),
    )
    for _ in range(2):
        gym.step(c1, actual_candidate_id="a")
        gym.step(c2, actual_candidate_id="b")

    key2 = contextual_regime_key(c2.state.state_addresses, c2.intervention.address)
    before2 = gym.regimes.get(key2)
    noisy = gym.step(c1, actual_candidate_id="noise", learn=True)
    assert noisy.current_regime.active.consequence_addresses == ("ea",)
    assert gym.regimes.get(key2) == before2


def test_contextual_gym_restart_is_deterministic_when_memory_and_regimes_are_restored():
    gym = ContextualLiveCognitiveGymV2(min_contiguous_support=2)
    req = _request(
        "c",
        ("x", "y"),
        "act:new",
        (("a", ("ea",), ("x", "ea")), ("b", ("eb",), ("x", "eb"))),
    )
    gym.step(req, actual_candidate_id="a")
    gym.step(req, actual_candidate_id="a")

    restored = ContextualLiveCognitiveGymV2(
        memory=gym.memory.restore(gym.memory.snapshot()),
        min_contiguous_support=2,
        regimes=gym.regimes,
    )
    a = gym.step(req, actual_candidate_id="a", learn=False)
    b = restored.step(req, actual_candidate_id="a", learn=False)
    assert a.context_key == b.context_key
    assert a.prior_regime == b.prior_regime
    assert a.effective_prediction.reason == b.effective_prediction.reason
    assert a.effective_prediction.resolved_candidate == b.effective_prediction.resolved_candidate
    assert a.error == b.error
    assert a.attention == b.attention
