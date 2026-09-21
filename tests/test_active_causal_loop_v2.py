from memoria_resolutiva.active_causal_experiment_v2 import InterventionOption
from memoria_resolutiva.active_causal_loop_v2 import CausalHypothesis, run_active_causal_loop


def _options(_active):
    return (
        InterventionOption("act:probe", (("out:A",), ("out:B",)), True),
    )


def test_active_loop_resolves_competing_hypotheses():
    result = run_active_causal_loop(
        hypotheses=(
            CausalHypothesis("H1", ("out:A",)),
            CausalHypothesis("H2", ("out:B",)),
        ),
        options_provider=_options,
        execute_intervention=lambda _address: ("out:B",),
    )
    assert result.resolved is True
    assert result.exhausted is False
    assert result.surviving_hypotheses == ("H2",)
    assert result.steps[0].eliminated_hypotheses == ("H1",)
    assert result.steps[0].reason == "ambiguity-resolved-by-active-experiment"


def test_unexpected_observation_exhausts_without_marking_history_false():
    result = run_active_causal_loop(
        hypotheses=(
            CausalHypothesis("H1", ("out:A",)),
            CausalHypothesis("H2", ("out:B",)),
        ),
        options_provider=_options,
        execute_intervention=lambda _address: ("out:Z",),
    )
    assert result.exhausted is True
    assert result.resolved is False
    assert result.surviving_hypotheses == ()
    assert result.reason == "observation-exhausted-active-hypotheses"


def test_no_discriminative_intervention_stops_without_guessing():
    result = run_active_causal_loop(
        hypotheses=(
            CausalHypothesis("H1", ("out:A",)),
            CausalHypothesis("H2", ("out:B",)),
        ),
        options_provider=lambda _active: (
            InterventionOption("act:bad", (("out:A",),), True),
        ),
        execute_intervention=lambda _address: ("out:A",),
    )
    assert result.resolved is False
    assert result.exhausted is False
    assert result.surviving_hypotheses == ("H1", "H2")
    assert result.steps[0].intervention_address is None


def test_single_hypothesis_requires_no_extra_experiment():
    calls = []
    result = run_active_causal_loop(
        hypotheses=(CausalHypothesis("H1", ("out:A",)),),
        options_provider=lambda _active: (),
        execute_intervention=lambda address: calls.append(address) or ("out:A",),
    )
    assert result.resolved is True
    assert result.steps == ()
    assert calls == []


def test_active_loop_is_deterministic_under_hypothesis_order():
    a = run_active_causal_loop(
        hypotheses=(
            CausalHypothesis("H2", ("out:B",)),
            CausalHypothesis("H1", ("out:A",)),
        ),
        options_provider=_options,
        execute_intervention=lambda _address: ("out:A",),
    )
    b = run_active_causal_loop(
        hypotheses=(
            CausalHypothesis("H1", ("out:A",)),
            CausalHypothesis("H2", ("out:B",)),
        ),
        options_provider=_options,
        execute_intervention=lambda _address: ("out:A",),
    )
    assert a == b


def test_world_cannot_return_empty_observation():
    try:
        run_active_causal_loop(
            hypotheses=(
                CausalHypothesis("H1", ("out:A",)),
                CausalHypothesis("H2", ("out:B",)),
            ),
            options_provider=_options,
            execute_intervention=lambda _address: (),
        )
    except ValueError as exc:
        assert "empty observation" in str(exc)
    else:
        raise AssertionError("expected ValueError")
