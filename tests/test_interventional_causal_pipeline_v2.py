from memoria_resolutiva.interventional_causal_pipeline_v2 import InterventionalCausalPipelineV2
from memoria_resolutiva.temporal_causal_window_v2 import TemporalCausalEvent


def _event(tick, episode, address, kind):
    return TemporalCausalEvent(
        tick=tick,
        episode_id=episode,
        agent_id="agent",
        address=address,
        kind=kind,
    )


def _seed_observational(pipeline):
    for episode, base in (("e1", 0), ("e2", 10)):
        pipeline.observational.observe_event(_event(base, episode, "x", "intervention"))
        pipeline.observational.observe_event(_event(base + 1, episode, "y", "observation"))


def test_observational_support_is_not_automatically_interventional_support():
    pipeline = InterventionalCausalPipelineV2()
    _seed_observational(pipeline)
    result = pipeline.assess(
        source_address="x",
        target_address="y",
        context_signature=("ctx",),
    )
    assert result.supported is True
    assert result.level == "observational"
    assert result.reversible is False


def test_deliberate_intervention_promotes_only_after_independent_trials():
    pipeline = InterventionalCausalPipelineV2()
    _seed_observational(pipeline)
    for trial in ("t1", "t2"):
        pipeline.observe_interventional_trial(
            trial_id=trial,
            context_signature=("ctx",),
            intervention_address="x",
            intervention_applied=True,
            target_observation=("y",),
        )
    result = pipeline.assess(
        source_address="x",
        target_address="y",
        context_signature=("ctx",),
    )
    assert result.level == "intervention-supported"
    assert result.reversible is False


def test_withdrawal_contrast_promotes_reversible_interventional_evidence():
    pipeline = InterventionalCausalPipelineV2()
    _seed_observational(pipeline)
    for trial in ("t1", "t2"):
        pipeline.observe_interventional_trial(
            trial_id=trial,
            context_signature=("ctx",),
            intervention_address="x",
            intervention_applied=True,
            target_observation=("y",),
        )
    pipeline.observe_interventional_trial(
        trial_id="w1",
        context_signature=("ctx",),
        intervention_address="x",
        intervention_applied=False,
        target_observation=("not-y",),
    )
    result = pipeline.assess(
        source_address="x",
        target_address="y",
        context_signature=("ctx",),
    )
    assert result.level == "reversible-intervention-supported"
    assert result.reversible is True


def test_target_persisting_without_intervention_blocks_interventional_promotion():
    pipeline = InterventionalCausalPipelineV2()
    _seed_observational(pipeline)
    for trial in ("t1", "t2"):
        pipeline.observe_interventional_trial(
            trial_id=trial,
            context_signature=("ctx",),
            intervention_address="x",
            intervention_applied=True,
            target_observation=("y",),
        )
    pipeline.observe_interventional_trial(
        trial_id="w1",
        context_signature=("ctx",),
        intervention_address="x",
        intervention_applied=False,
        target_observation=("y",),
    )
    result = pipeline.assess(
        source_address="x",
        target_address="y",
        context_signature=("ctx",),
    )
    assert result.level == "observational"
    assert result.interventional.reason == "target-persists-without-intervention"


def test_intervention_cannot_rescue_failed_observational_gate():
    pipeline = InterventionalCausalPipelineV2()
    for trial in ("t1", "t2"):
        pipeline.observe_interventional_trial(
            trial_id=trial,
            context_signature=("ctx",),
            intervention_address="x",
            intervention_applied=True,
            target_observation=("y",),
        )
    result = pipeline.assess(
        source_address="x",
        target_address="y",
        context_signature=("ctx",),
    )
    assert result.supported is False
    assert result.level == "unsupported"
