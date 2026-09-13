from memoria_resolutiva.continuous_causal_pipeline_v2 import ContinuousCausalPipelineV2
from memoria_resolutiva.temporal_causal_window_v2 import TemporalCausalEvent


def _event(tick: int, episode_id: str, agent: str, address: str, kind: str):
    return TemporalCausalEvent(
        tick=tick,
        episode_id=episode_id,
        agent_id=agent,
        address=address,
        kind=kind,
    )


def test_recurrent_direct_path_becomes_supported_without_negative_control():
    pipe = ContinuousCausalPipelineV2(max_tick_distance=3, min_independent_exposed=2)
    pipe.observe_event(_event(0, "E1", "A", "x", "intervention"))
    pipe.observe_event(_event(1, "E1", "B", "y", "observation"))
    pipe.observe_event(_event(2, "E2", "A", "x", "intervention"))
    pipe.observe_event(_event(3, "E2", "B", "y", "observation"))
    result = pipe.resolve(source_address="x", target_address="y")
    assert result.recurrent is True
    assert result.contrast_supported is True
    assert result.supported is True


def test_single_episode_does_not_count_as_independent_recurrence():
    pipe = ContinuousCausalPipelineV2(max_tick_distance=3, min_independent_exposed=2)
    pipe.observe_event(_event(0, "E1", "A", "x", "intervention"))
    pipe.observe_event(_event(1, "E1", "B", "y", "observation"))
    result = pipe.resolve(source_address="x", target_address="y")
    assert result.supported is False
    assert result.reason == "insufficient-independent-path-recurrence"


def test_negative_control_blocks_previously_supported_relation():
    pipe = ContinuousCausalPipelineV2(max_tick_distance=3, min_independent_exposed=2)
    for base, eid in ((0, "E1"), (2, "E2")):
        pipe.observe_event(_event(base, eid, "A", "x", "intervention"))
        pipe.observe_event(_event(base + 1, eid, "B", "y", "observation"))
    assert pipe.resolve(source_address="x", target_address="y").supported is True
    pipe.observe_negative_control(episode_id="C1", source_address="x", target_address="y")
    blocked = pipe.resolve(source_address="x", target_address="y")
    assert blocked.supported is False
    assert blocked.reason == "target-also-occurs-without-intervention"


def test_multistep_shape_requires_matching_mediator_structure():
    pipe = ContinuousCausalPipelineV2(max_tick_distance=3, min_independent_exposed=2)
    pipe.observe_event(_event(0, "E1", "A", "x", "intervention"))
    pipe.observe_event(_event(1, "E1", "W", "m", "mediator"))
    pipe.observe_event(_event(2, "E1", "B", "y", "observation"))
    pipe.observe_event(_event(3, "E2", "A", "x", "intervention"))
    pipe.observe_event(_event(4, "E2", "W", "m", "mediator"))
    pipe.observe_event(_event(5, "E2", "B", "y", "observation"))
    supported = pipe.resolve(source_address="x", mediator_addresses=("m",), target_address="y")
    wrong_shape = pipe.resolve(source_address="x", mediator_addresses=("other",), target_address="y")
    assert supported.supported is True
    assert wrong_shape.supported is False


def test_controls_for_other_target_do_not_block_relation():
    pipe = ContinuousCausalPipelineV2(max_tick_distance=3, min_independent_exposed=2)
    for base, eid in ((0, "E1"), (2, "E2")):
        pipe.observe_event(_event(base, eid, "A", "x", "intervention"))
        pipe.observe_event(_event(base + 1, eid, "B", "y", "observation"))
    pipe.observe_negative_control(episode_id="C1", source_address="x", target_address="z")
    assert pipe.resolve(source_address="x", target_address="y").supported is True


def test_pipeline_is_deterministic():
    def build():
        pipe = ContinuousCausalPipelineV2(max_tick_distance=3, min_independent_exposed=2)
        for base, eid in ((0, "E1"), (2, "E2")):
            pipe.observe_event(_event(base, eid, "A", "x", "intervention"))
            pipe.observe_event(_event(base + 1, eid, "B", "y", "observation"))
        return pipe.resolve(source_address="x", target_address="y")
    assert build() == build()
