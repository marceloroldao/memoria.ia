from memoria_resolutiva.contextual_temporal_regime_v2 import (
    ContextualTemporalRegimes,
    contextual_regime_key,
    observe_contextual_regime,
)
from memoria_resolutiva.world_state_candidate_resolution_v2 import WorldStateCandidate


def _candidate(name: str) -> WorldStateCandidate:
    return WorldStateCandidate(
        candidate_id=name,
        consequence_addresses=(f"effect:{name}",),
        next_state_addresses=("world:anchor", f"effect:{name}"),
    )


def test_structurally_distinct_contexts_keep_independent_regimes():
    regimes = ContextualTemporalRegimes.empty()
    s1 = ("zone:a", "anchor:a")
    s2 = ("zone:b", "zone:b")
    for _ in range(2):
        regimes = observe_contextual_regime(regimes, s1, "action:step", _candidate("a"))
        regimes = observe_contextual_regime(regimes, s2, "action:step", _candidate("b"))

    k1 = contextual_regime_key(s1, "action:step")
    k2 = contextual_regime_key(s2, "action:step")
    assert k1 != k2
    assert regimes.get(k1).active is not None
    assert regimes.get(k1).active.consequence_addresses == ("effect:a",)
    assert regimes.get(k2).active is not None
    assert regimes.get(k2).active.consequence_addresses == ("effect:b",)


def test_literal_renaming_with_same_topology_reuses_same_regime_context():
    a = contextual_regime_key(("x", "y"), "action:q")
    b = contextual_regime_key(("p", "q"), "action:z")
    assert a == b


def test_intervention_role_splits_context_even_when_state_topology_matches():
    state = ("x", "y")
    external = contextual_regime_key(state, "action:new")
    state_bound = contextual_regime_key(state, "x")
    assert external != state_bound


def test_noise_in_one_context_does_not_challenge_other_context_regime():
    regimes = ContextualTemporalRegimes.empty()
    s1 = ("zone:a", "anchor:a")
    s2 = ("zone:b", "zone:b")
    for _ in range(2):
        regimes = observe_contextual_regime(regimes, s1, "action:step", _candidate("a"))
        regimes = observe_contextual_regime(regimes, s2, "action:step", _candidate("b"))

    k1 = contextual_regime_key(s1, "action:step")
    k2 = contextual_regime_key(s2, "action:step")
    before_other = regimes.get(k2)
    regimes = observe_contextual_regime(regimes, s1, "action:step", _candidate("noise"))
    assert regimes.get(k1).active.consequence_addresses == ("effect:a",)
    assert regimes.get(k2) == before_other


def test_contextual_regime_collection_is_deterministic():
    sequence = (
        (("a", "b"), "act", "x"),
        (("c", "c"), "act", "y"),
        (("a", "b"), "act", "x"),
        (("c", "c"), "act", "y"),
    )
    results = []
    for _ in range(2):
        regimes = ContextualTemporalRegimes.empty()
        for state, intervention, candidate in sequence:
            regimes = observe_contextual_regime(
                regimes,
                state,
                intervention,
                _candidate(candidate),
            )
        results.append(regimes)
    assert results[0] == results[1]
