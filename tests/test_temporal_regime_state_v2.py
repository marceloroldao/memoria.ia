from memoria_resolutiva.temporal_regime_state_v2 import (
    TemporalRegimeState,
    constrain_prediction_to_active_regime,
    observe_regime,
)
from memoria_resolutiva.world_state_candidate_resolution_v2 import (
    WorldStateCandidate,
    WorldStateCandidateMatch,
    WorldStateCandidateResolution,
)
from memoria_resolutiva.structural_intervention_transfer_v2 import StructuralInterventionResolution, StructuralInterventionKey


def _candidate(name: str) -> WorldStateCandidate:
    return WorldStateCandidate(name, (f"effect:{name}",), ("world:anchor", f"effect:{name}"))


def _resolution(*candidates: WorldStateCandidate) -> WorldStateCandidateResolution:
    structural = StructuralInterventionResolution(
        query_key=StructuralInterventionKey(2, (0, 1), "novel-to-state"),
        patterns=(),
        resolved=False,
        ambiguous=False,
        reason="fixture",
    )
    matches = tuple(WorldStateCandidateMatch(candidate, ()) for candidate in candidates)
    return WorldStateCandidateResolution(
        structural=structural,
        matches=matches,
        resolved_candidate=None,
        resolved=False,
        ambiguous=len(matches) > 1,
        reason="fixture",
    )


def test_two_contiguous_observations_form_initial_regime():
    state = TemporalRegimeState.empty()
    state = observe_regime(state, _candidate("a"))
    assert state.active is None
    state = observe_regime(state, _candidate("a"))
    assert state.active is not None
    assert state.active.consequence_addresses == ("effect:a",)
    assert state.generation == 1


def test_single_anomaly_does_not_replace_active_regime():
    state = TemporalRegimeState.empty()
    state = observe_regime(state, _candidate("a"))
    state = observe_regime(state, _candidate("a"))
    challenged = observe_regime(state, _candidate("b"))
    assert challenged.active == state.active
    assert challenged.pending is not None
    assert challenged.pending.consequence_addresses == ("effect:b",)
    assert challenged.switches == 0


def test_sustained_alternative_switches_regime_without_erasing_history():
    state = TemporalRegimeState.empty()
    for name in ("a", "a", "b", "b"):
        state = observe_regime(state, _candidate(name))
    assert state.active is not None
    assert state.active.consequence_addresses == ("effect:b",)
    assert state.switches == 1
    assert state.generation == 2


def test_old_regime_can_be_reactivated_in_later_context():
    state = TemporalRegimeState.empty()
    for name in ("a", "a", "b", "b", "a", "a"):
        state = observe_regime(state, _candidate(name))
    assert state.active is not None
    assert state.active.consequence_addresses == ("effect:a",)
    assert state.switches == 2


def test_active_regime_narrows_structural_ambiguity_without_inventing_candidate():
    a, b = _candidate("a"), _candidate("b")
    state = TemporalRegimeState.empty()
    state = observe_regime(state, a)
    state = observe_regime(state, a)
    narrowed = constrain_prediction_to_active_regime(_resolution(a, b), state)
    assert narrowed.resolved is True
    assert narrowed.ambiguous is False
    assert narrowed.resolved_candidate == a
    assert narrowed.reason == "active-temporal-regime"


def test_absent_active_regime_candidate_does_not_force_prediction():
    a, b = _candidate("a"), _candidate("b")
    state = TemporalRegimeState.empty()
    state = observe_regime(state, a)
    state = observe_regime(state, a)
    original = _resolution(b)
    assert constrain_prediction_to_active_regime(original, state) == original


def test_regime_state_is_deterministic():
    sequence = tuple(_candidate(name) for name in ("a", "a", "b", "a", "b", "b", "b"))
    states = []
    for _ in range(2):
        state = TemporalRegimeState.empty()
        for candidate in sequence:
            state = observe_regime(state, candidate)
        states.append(state)
    assert states[0] == states[1]
