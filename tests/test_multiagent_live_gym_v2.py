from memoria_resolutiva.live_infinita_adapter_v2 import make_live_request
from memoria_resolutiva.multiagent_live_gym_v2 import (
    AgentContextualRegimes,
    MultiAgentLiveCognitiveGymV2,
    MultiAgentObservation,
)


def _request(prefix: str, index: int, *, repeated_state: bool = False):
    state = (f"{prefix}:zone", f"{prefix}:zone") if repeated_state else (f"{prefix}:zone", f"{prefix}:anchor")
    return make_live_request(
        frame_id=f"{prefix}:F{index}",
        state_addresses=state,
        intervention_id=f"{prefix}:I{index}",
        intervention_address=f"{prefix}:action",
        candidates=(
            ("a", (f"{prefix}:effect:a",), (state[0], f"{prefix}:effect:a")),
            ("b", (f"{prefix}:effect:b",), (state[0], f"{prefix}:effect:b")),
        ),
        provenance="multiagent-live-gym-v2",
    )


def _obs(agent: str, prefix: str, index: int, actual: str, *, repeated_state: bool = False):
    return MultiAgentObservation(agent, _request(prefix, index, repeated_state=repeated_state), actual)


def test_simultaneous_agents_do_not_learn_from_batch_order():
    gym = MultiAgentLiveCognitiveGymV2(min_independent_episodes=1)
    steps = gym.step_batch(
        (
            _obs("agent:b", "b", 0, "b"),
            _obs("agent:a", "a", 0, "a"),
        ),
        learn=True,
    )
    assert tuple(step.agent_id for step in steps) == ("agent:a", "agent:b")
    # Both predictions are made against the same pre-tick empty memory.
    assert all(step.error.kind == "unconstrained-observation" for step in steps)
    assert len(gym.memory.snapshot()) == 2


def test_agents_can_hold_different_active_regimes_in_same_structural_context():
    gym = MultiAgentLiveCognitiveGymV2(min_independent_episodes=1, min_contiguous_support=2)
    for index in range(2):
        gym.step_batch(
            (
                _obs("agent:a", "a", index, "a"),
                _obs("agent:b", "b", index, "b"),
            )
        )

    third = gym.step_batch(
        (
            _obs("agent:a", "a", 2, "a"),
            _obs("agent:b", "b", 2, "b"),
        ),
        learn=False,
    )
    by_agent = {step.agent_id: step for step in third}
    assert by_agent["agent:a"].current_regime.active.consequence_addresses == ("a:effect:a",)
    assert by_agent["agent:b"].current_regime.active.consequence_addresses == ("b:effect:b",)
    assert by_agent["agent:a"].effective_prediction.resolved is True
    assert by_agent["agent:b"].effective_prediction.resolved is True


def test_noise_for_one_agent_does_not_reorient_other_agent():
    gym = MultiAgentLiveCognitiveGymV2(min_independent_episodes=1, min_contiguous_support=2)
    for index in range(2):
        gym.step_batch(
            (
                _obs("agent:a", "a", index, "a"),
                _obs("agent:b", "b", index, "b"),
            )
        )
    before_b = gym.agent_regimes.get("agent:b")
    step = gym.step_batch((_obs("agent:a", "a", 3, "b"),), learn=False)[0]
    assert step.current_regime.active.consequence_addresses == ("a:effect:a",)
    assert step.current_regime.pending is not None
    assert gym.agent_regimes.get("agent:b") == before_b


def test_structurally_distinct_contexts_remain_local_inside_one_agent():
    gym = MultiAgentLiveCognitiveGymV2(min_independent_episodes=1, min_contiguous_support=2)
    for index in range(2):
        gym.step_batch((_obs("agent:a", "x", index, "a", repeated_state=False),))
        gym.step_batch((_obs("agent:a", "y", index, "b", repeated_state=True),))
    regimes = gym.agent_regimes.get("agent:a")
    assert len(regimes.entries) == 2
    active = {state.active.consequence_addresses for _, state in regimes.entries if state.active is not None}
    assert active == {("x:effect:a",), ("y:effect:b",)}


def test_batch_order_does_not_change_multiagent_cognitive_state():
    def run(reverse: bool):
        gym = MultiAgentLiveCognitiveGymV2(min_independent_episodes=1)
        batch = (
            _obs("agent:a", "a", 0, "a"),
            _obs("agent:b", "b", 0, "b"),
        )
        gym.step_batch(tuple(reversed(batch)) if reverse else batch)
        gym.step_batch(tuple(reversed(batch)) if reverse else batch)
        return gym.memory.snapshot(), gym.agent_regimes

    memory_a, regimes_a = run(False)
    memory_b, regimes_b = run(True)
    assert memory_a == memory_b
    assert regimes_a == regimes_b


def test_multiagent_state_restores_deterministically():
    gym = MultiAgentLiveCognitiveGymV2(min_independent_episodes=1)
    for index in range(2):
        gym.step_batch(
            (
                _obs("agent:a", "a", index, "a"),
                _obs("agent:b", "b", index, "b"),
            )
        )

    restored = MultiAgentLiveCognitiveGymV2(
        memory=gym.memory.restore(gym.memory.snapshot()),
        min_independent_episodes=1,
        agent_regimes=gym.agent_regimes,
    )
    request = (
        _obs("agent:a", "a", 10, "a"),
        _obs("agent:b", "b", 10, "b"),
    )
    a = gym.step_batch(request, learn=False)
    b = restored.step_batch(request, learn=False)
    assert a == b


def test_duplicate_agent_inside_same_tick_fails_closed():
    gym = MultiAgentLiveCognitiveGymV2()
    try:
        gym.step_batch(
            (
                _obs("agent:a", "a", 0, "a"),
                _obs("agent:a", "a", 1, "a"),
            )
        )
    except ValueError as exc:
        assert "one observation per agent" in str(exc)
    else:
        raise AssertionError("expected ValueError")
