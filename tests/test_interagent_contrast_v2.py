from memoria_resolutiva.interagent_contrast_v2 import InteragentContrastMemory


def test_recurrent_exposure_without_negative_control_is_supported():
    memory = InteragentContrastMemory()
    for episode_id in ("E1", "E2"):
        memory.observe(
            episode_id=episode_id,
            source_intervention_present=True,
            target_observation=("obs:y",),
        )
    result = memory.resolve(target_observation=("obs:y",))
    assert result.supported is True
    assert result.discriminative is True
    assert result.reason == "exposure-specific-recurrence"


def test_target_seen_without_intervention_blocks_causal_promotion():
    memory = InteragentContrastMemory()
    for episode_id in ("E1", "E2"):
        memory.observe(
            episode_id=episode_id,
            source_intervention_present=True,
            target_observation=("obs:y",),
        )
    memory.observe(
        episode_id="C1",
        source_intervention_present=False,
        target_observation=("obs:y",),
    )
    result = memory.resolve(target_observation=("obs:y",))
    assert result.supported is False
    assert result.discriminative is False
    assert result.reason == "target-also-occurs-without-intervention"


def test_repeated_same_episode_does_not_fake_independent_support():
    memory = InteragentContrastMemory()
    for _ in range(5):
        memory.observe(
            episode_id="E1",
            source_intervention_present=True,
            target_observation=("obs:y",),
        )
    result = memory.resolve(target_observation=("obs:y",))
    assert result.supported is False
    assert result.exposed_episodes == ("E1",)


def test_unrelated_control_observation_does_not_block_target():
    memory = InteragentContrastMemory()
    for episode_id in ("E1", "E2"):
        memory.observe(
            episode_id=episode_id,
            source_intervention_present=True,
            target_observation=("obs:y",),
        )
    memory.observe(
        episode_id="C1",
        source_intervention_present=False,
        target_observation=("obs:z",),
    )
    result = memory.resolve(target_observation=("obs:y",))
    assert result.supported is True


def test_restart_is_deterministic():
    memory = InteragentContrastMemory()
    memory.observe(
        episode_id="E1",
        source_intervention_present=True,
        target_observation=("obs:y",),
    )
    memory.observe(
        episode_id="E2",
        source_intervention_present=True,
        target_observation=("obs:y",),
    )
    restored = InteragentContrastMemory.restore(memory.snapshot())
    assert restored.resolve(target_observation=("obs:y",)) == memory.resolve(
        target_observation=("obs:y",)
    )
