from memoria_resolutiva.active_causal_experiment_v2 import (
    InterventionOption,
    select_active_causal_experiment,
)


def test_requires_competing_hypotheses():
    result = select_active_causal_experiment(
        hypothesis_outcomes=(("h1", ("y",)),),
        options=(InterventionOption("x", (("y",), ("z",))),),
    )
    assert result.active is False
    assert result.reason == "insufficient-competing-hypotheses"


def test_chooses_available_discriminative_intervention():
    result = select_active_causal_experiment(
        hypothesis_outcomes=(("h1", ("y",)), ("h2", ("z",))),
        options=(
            InterventionOption("a", (("y",),)),
            InterventionOption("b", (("y",), ("z",))),
        ),
    )
    assert result.active is True
    assert result.intervention_address == "b"
    assert result.discriminative_outcomes == (("y",), ("z",))


def test_never_selects_unavailable_intervention():
    result = select_active_causal_experiment(
        hypothesis_outcomes=(("h1", ("y",)), ("h2", ("z",))),
        options=(
            InterventionOption("best", (("y",), ("z",)), available=False),
            InterventionOption("usable", (("y",), ("z",))),
        ),
    )
    assert result.intervention_address == "usable"


def test_non_discriminative_options_fail_closed():
    result = select_active_causal_experiment(
        hypothesis_outcomes=(("h1", ("y",)), ("h2", ("z",))),
        options=(InterventionOption("a", (("y",),)),),
    )
    assert result.active is False
    assert result.reason == "no-discriminative-available-intervention"


def test_selection_is_deterministic_under_option_order():
    hypotheses = (("h1", ("y",)), ("h2", ("z",)))
    a = select_active_causal_experiment(
        hypothesis_outcomes=hypotheses,
        options=(
            InterventionOption("b", (("y",), ("z",))),
            InterventionOption("a", (("y",), ("z",))),
        ),
    )
    b = select_active_causal_experiment(
        hypothesis_outcomes=hypotheses,
        options=(
            InterventionOption("a", (("y",), ("z",))),
            InterventionOption("b", (("y",), ("z",))),
        ),
    )
    assert a == b
    assert a.intervention_address == "a"
