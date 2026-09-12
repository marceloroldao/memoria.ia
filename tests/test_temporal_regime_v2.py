from memoria_resolutiva.temporal_regime_v2 import (
    initial_temporal_regime,
    observe_temporal_regime,
)


def test_regime_requires_contiguous_support_before_activation():
    state = initial_temporal_regime()
    u1 = observe_temporal_regime(state, "a", min_contiguous_support=2)
    assert u1.current.active_key is None
    assert u1.current.challenger_key == "a"
    u2 = observe_temporal_regime(u1.current, "a", min_contiguous_support=2)
    assert u2.current.active_key == "a"
    assert u2.switched is True
    assert u2.event == "regime-established"


def test_single_conflicting_observation_does_not_replace_active_regime():
    state = initial_temporal_regime()
    state = observe_temporal_regime(state, "a", min_contiguous_support=2).current
    state = observe_temporal_regime(state, "a", min_contiguous_support=2).current
    update = observe_temporal_regime(state, "b", min_contiguous_support=2)
    assert update.current.active_key == "a"
    assert update.current.challenger_key == "b"
    assert update.current.challenger_streak == 1
    assert update.switched is False


def test_contiguous_competitor_forms_new_regime_without_erasing_old_history():
    state = initial_temporal_regime()
    for key in ("a", "a", "a", "b"):
        state = observe_temporal_regime(state, key, min_contiguous_support=2).current
    update = observe_temporal_regime(state, "b", min_contiguous_support=2)
    assert update.current.active_key == "b"
    assert update.current.generation == 2
    assert update.event == "regime-switched"
    assert update.switched is True


def test_interrupted_challenger_loses_contiguous_support():
    state = initial_temporal_regime()
    for key in ("a", "a", "b", "a", "b"):
        state = observe_temporal_regime(state, key, min_contiguous_support=2).current
    assert state.active_key == "a"
    assert state.challenger_key == "b"
    assert state.challenger_streak == 1
