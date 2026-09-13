from memoria_resolutiva.situated_contextual_regime_v2 import (
    SituatedContextualRegimes,
    observe_situated_regime,
    situated_context_key,
)
from memoria_resolutiva.world_state_candidate_resolution_v2 import WorldStateCandidate


def _candidate(cid: str, consequence: str) -> WorldStateCandidate:
    return WorldStateCandidate(
        candidate_id=cid,
        consequence_addresses=(consequence,),
        next_state_addresses=("agent", consequence),
    )


def test_isomorphic_r1_r2_share_structural_key_but_not_situated_key():
    r1 = situated_context_key(("agent", "region:r1"), "action:probe")
    r2 = situated_context_key(("agent", "region:r2"), "action:probe")
    assert r1.structural_key == r2.structural_key
    assert r1 != r2


def test_r1_and_r2_maintain_independent_active_regimes():
    regimes = SituatedContextualRegimes.empty()
    for _ in range(2):
        regimes = observe_situated_regime(
            regimes,
            ("agent", "region:r1"),
            "action:probe",
            _candidate("x", "effect:x"),
            min_contiguous_support=2,
        )
    for _ in range(2):
        regimes = observe_situated_regime(
            regimes,
            ("agent", "region:r2"),
            "action:probe",
            _candidate("y", "effect:y"),
            min_contiguous_support=2,
        )

    r1 = regimes.get(situated_context_key(("agent", "region:r1"), "action:probe"))
    r2 = regimes.get(situated_context_key(("agent", "region:r2"), "action:probe"))
    assert r1.active_consequence_addresses == ("effect:x",)
    assert r2.active_consequence_addresses == ("effect:y",)


def test_return_to_r1_recovers_prior_local_regime_without_relearning():
    regimes = SituatedContextualRegimes.empty()
    for _ in range(2):
        regimes = observe_situated_regime(
            regimes,
            ("agent", "region:r1"),
            "action:probe",
            _candidate("x", "effect:x"),
            min_contiguous_support=2,
        )
    for _ in range(2):
        regimes = observe_situated_regime(
            regimes,
            ("agent", "region:r2"),
            "action:probe",
            _candidate("y", "effect:y"),
            min_contiguous_support=2,
        )

    before_return = regimes.get(situated_context_key(("agent", "region:r1"), "action:probe"))
    after_return = regimes.get(situated_context_key(("agent", "region:r1"), "action:probe"))
    assert before_return == after_return
    assert after_return.active_consequence_addresses == ("effect:x",)


def test_noise_in_r1_does_not_modify_r2_local_regime():
    regimes = SituatedContextualRegimes.empty()
    for _ in range(2):
        regimes = observe_situated_regime(
            regimes,
            ("agent", "region:r2"),
            "action:probe",
            _candidate("y", "effect:y"),
            min_contiguous_support=2,
        )
    r2_key = situated_context_key(("agent", "region:r2"), "action:probe")
    before = regimes.get(r2_key)
    regimes = observe_situated_regime(
        regimes,
        ("agent", "region:r1"),
        "action:probe",
        _candidate("noise", "effect:z"),
        min_contiguous_support=2,
    )
    assert regimes.get(r2_key) == before
