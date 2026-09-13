from memoria_resolutiva.continuous_temporal_causal_buffer_v2 import (
    CausalBufferState,
    append_event,
    candidate_paths_to_latest,
)
from memoria_resolutiva.temporal_causal_window_v2 import TemporalCausalEvent


def _event(tick: int, address: str, *, kind: str) -> TemporalCausalEvent:
    return TemporalCausalEvent(
        tick=tick,
        episode_id=f"ep:{tick}:{address}:{kind}",
        agent_id="agent:test",
        address=address,
        kind=kind,
    )


def test_direct_next_tick_path_is_visible():
    state = CausalBufferState.empty(max_tick_distance=3)
    state = append_event(state, _event(0, "x", kind="intervention"))
    state = append_event(state, _event(1, "y", kind="observation"))
    paths = candidate_paths_to_latest(state)
    assert len(paths) == 1
    assert paths[0].source.address == "x"
    assert paths[0].target.address == "y"


def test_multistep_path_requires_observable_mediator():
    state = CausalBufferState.empty(max_tick_distance=3)
    state = append_event(state, _event(0, "x", kind="intervention"))
    state = append_event(state, _event(1, "m", kind="mediator"))
    state = append_event(state, _event(2, "y", kind="observation"))
    paths = candidate_paths_to_latest(state)
    assert any(
        path.source.address == "x"
        and path.target.address == "y"
        and tuple(item.address for item in path.mediators) == ("m",)
        for path in paths
    )


def test_old_events_are_evicted_by_window():
    state = CausalBufferState.empty(max_tick_distance=2)
    state = append_event(state, _event(0, "old", kind="intervention"))
    state = append_event(state, _event(1, "m1", kind="mediator"))
    state = append_event(state, _event(2, "m2", kind="mediator"))
    state = append_event(state, _event(3, "target", kind="observation"))
    assert all(item.tick >= 1 for item in state.events)
    assert not any(path.source.address == "old" for path in candidate_paths_to_latest(state))


def test_same_tick_events_do_not_create_ordered_causal_path():
    state = CausalBufferState.empty(max_tick_distance=3)
    state = append_event(state, _event(1, "a", kind="intervention"))
    state = append_event(state, _event(1, "b", kind="observation"))
    assert candidate_paths_to_latest(state) == ()


def test_out_of_order_event_fails_closed():
    state = CausalBufferState.empty(max_tick_distance=3)
    state = append_event(state, _event(2, "a", kind="intervention"))
    try:
        append_event(state, _event(1, "b", kind="observation"))
    except ValueError as exc:
        assert "non-decreasing" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_buffer_is_deterministic():
    def build():
        state = CausalBufferState.empty(max_tick_distance=3)
        state = append_event(state, _event(0, "x", kind="intervention"))
        state = append_event(state, _event(1, "m", kind="mediator"))
        state = append_event(state, _event(2, "y", kind="observation"))
        return state, candidate_paths_to_latest(state)

    assert build() == build()
