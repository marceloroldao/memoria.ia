from memoria_resolutiva.intervention_consequence_v2 import InterventionConsequenceMemory
from memoria_resolutiva.live_cognitive_gym_v2 import LiveCognitiveGymV2
from memoria_resolutiva.live_infinita_adapter_v2 import make_live_request


def _request(frame_id, state, action, candidates):
    return make_live_request(
        frame_id=frame_id,
        state_addresses=state,
        intervention_id=f"i:{frame_id}",
        intervention_address=action,
        candidates=candidates,
        provenance="synthetic-live-gym",
    )


def test_gym_learns_after_observation_not_before_prediction():
    gym = LiveCognitiveGymV2(min_independent_episodes=2)
    req = _request(
        "f1",
        ("s0", "s1"),
        "a0",
        (("c-new", ("n0",), ("s0", "n0")),),
    )

    first = gym.step(req, actual_candidate_id="c-new")
    second = gym.step(req, actual_candidate_id="c-new")
    third = gym.step(req, actual_candidate_id="c-new", learn=False)

    assert first.prediction.resolved is False
    assert first.error.kind == "unconstrained-observation"
    assert second.prediction.resolved is False
    assert second.error.kind == "unconstrained-observation"
    assert third.prediction.resolved is True
    assert third.prediction.resolved_candidate.candidate_id == "c-new"
    assert third.error.kind == "prediction-confirmed"
    assert third.attention.level == "routine"


def test_structural_transfer_works_in_literal_new_world():
    gym = LiveCognitiveGymV2(min_independent_episodes=2)
    train = _request(
        "train",
        ("t0", "t1"),
        "ta",
        (("t-new", ("tn",), ("t0", "tn")),),
    )
    gym.step(train, actual_candidate_id="t-new")
    gym.step(train, actual_candidate_id="t-new")

    held = _request(
        "held",
        ("h0", "h1"),
        "ha",
        (
            ("wrong", ("h0",), ("h0", "h1")),
            ("right", ("hn",), ("h0", "hn")),
        ),
    )
    result = gym.step(held, actual_candidate_id="right", learn=False)

    assert result.prediction.resolved is True
    assert result.prediction.resolved_candidate.candidate_id == "right"
    assert result.error.kind == "prediction-confirmed"


def test_unexpected_real_world_candidate_causes_reorientation():
    memory = InterventionConsequenceMemory()
    memory.ingest_episode(("t0", "t1"), "ta", ("tn",), ("t0", "tn"))
    memory.ingest_episode(("u0", "u1"), "ua", ("un",), ("u0", "un"))
    gym = LiveCognitiveGymV2(memory, min_independent_episodes=2)

    req = _request(
        "surprise",
        ("h0", "h1"),
        "ha",
        (
            ("expected", ("hn",), ("h0", "hn")),
            ("actual", ("h0",), ("h0", "h1")),
        ),
    )
    result = gym.step(req, actual_candidate_id="actual", learn=False)

    assert result.prediction.resolved is True
    assert result.prediction.resolved_candidate.candidate_id == "expected"
    assert result.error.kind == "total-surprise"
    assert result.attention.level == "reorient"
    assert result.attention.requires_recovery is True


def test_ambiguous_world_candidates_reduce_after_observation():
    memory = InterventionConsequenceMemory()
    memory.ingest_episode(("t0", "t1"), "ta", ("tn",), ("t0", "tn"))
    memory.ingest_episode(("u0", "u1"), "ua", ("un",), ("u0", "un"))
    gym = LiveCognitiveGymV2(memory, min_independent_episodes=2)

    req = _request(
        "amb",
        ("h0", "h1"),
        "ha",
        (
            ("a", ("hn0",), ("h0", "hn0")),
            ("b", ("hn1",), ("h0", "hn1")),
        ),
    )
    result = gym.step(req, actual_candidate_id="a", learn=False)

    assert result.prediction.ambiguous is True
    assert result.error.kind == "hypothesis-reduction"
    assert result.attention.level == "informative"


def test_restart_preserves_gym_prediction():
    memory = InterventionConsequenceMemory()
    memory.ingest_episode(("t0", "t1"), "ta", ("tn",), ("t0", "tn"))
    memory.ingest_episode(("u0", "u1"), "ua", ("un",), ("u0", "un"))
    restored = InterventionConsequenceMemory.restore(memory.snapshot())

    req = _request(
        "restart",
        ("h0", "h1"),
        "ha",
        (("right", ("hn",), ("h0", "hn")),),
    )
    a = LiveCognitiveGymV2(memory).step(req, actual_candidate_id="right", learn=False)
    b = LiveCognitiveGymV2(restored).step(req, actual_candidate_id="right", learn=False)

    assert a.prediction == b.prediction
    assert a.error == b.error
    assert a.attention == b.attention
