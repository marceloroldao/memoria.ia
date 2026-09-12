from memoria_resolutiva.temporal_causal_window_v2 import TemporalCausalEvent, evaluate_temporal_causal_path


def _event(tick: int, kind: str, address: str, agent: str = "agent:a") -> TemporalCausalEvent:
    return TemporalCausalEvent(tick, f"E{tick}:{kind}:{address}", agent, address, kind)


def test_direct_next_tick_path_is_allowed_without_mediator():
    source = _event(0, "intervention", "act:x")
    target = _event(1, "observation", "obs:y", "agent:b")
    path = evaluate_temporal_causal_path(source, target)
    assert path.supported is True
    assert path.distance == 1
    assert path.mediated is False


def test_multistep_path_requires_observable_mediator():
    source = _event(0, "intervention", "act:x")
    target = _event(2, "observation", "obs:y", "agent:b")
    path = evaluate_temporal_causal_path(source, target)
    assert path.supported is False
    assert path.reason == "missing-observable-mediator"


def test_multistep_path_with_mediator_is_supported():
    source = _event(0, "intervention", "act:x")
    mediator = _event(1, "mediator", "world:changed", "world")
    target = _event(2, "observation", "obs:y", "agent:b")
    path = evaluate_temporal_causal_path(source, target, mediators=(mediator,))
    assert path.supported is True
    assert path.mediators == (mediator,)
    assert path.reason == "bounded-mediated-path"


def test_old_event_outside_window_cannot_claim_late_effect():
    source = _event(0, "intervention", "act:x")
    mediator = _event(3, "mediator", "world:changed", "world")
    target = _event(5, "observation", "obs:y", "agent:b")
    path = evaluate_temporal_causal_path(source, target, mediators=(mediator,), max_tick_distance=3)
    assert path.supported is False
    assert path.reason == "outside-temporal-window"


def test_future_or_same_tick_target_is_not_treated_as_forward_causal_path():
    source = _event(2, "intervention", "act:x")
    same = _event(2, "observation", "obs:y", "agent:b")
    earlier = _event(1, "observation", "obs:y", "agent:b")
    assert evaluate_temporal_causal_path(source, same).reason == "non-forward-time"
    assert evaluate_temporal_causal_path(source, earlier).reason == "non-forward-time"


def test_mediators_outside_source_target_interval_are_ignored():
    source = _event(0, "intervention", "act:x")
    before = _event(0, "mediator", "m:before", "world")
    inside = _event(1, "mediator", "m:inside", "world")
    after = _event(3, "mediator", "m:after", "world")
    target = _event(2, "observation", "obs:y", "agent:b")
    path = evaluate_temporal_causal_path(source, target, mediators=(after, before, inside))
    assert path.supported is True
    assert path.mediators == (inside,)


def test_path_evaluation_is_deterministic_under_mediator_order():
    source = _event(0, "intervention", "act:x")
    m1 = _event(1, "mediator", "m:a", "world")
    m2 = _event(1, "mediator", "m:b", "world")
    target = _event(2, "observation", "obs:y", "agent:b")
    a = evaluate_temporal_causal_path(source, target, mediators=(m2, m1))
    b = evaluate_temporal_causal_path(source, target, mediators=(m1, m2))
    assert a == b
