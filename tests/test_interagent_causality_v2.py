from memoria_resolutiva.interagent_causality_v2 import InteragentCausalMemory


def test_single_temporal_cooccurrence_is_not_promoted_to_causality():
    memory = InteragentCausalMemory()
    memory.observe(
        episode_id="E1",
        source_agent="A",
        source_intervention="action:x",
        target_agent="B",
        target_observation=("obs:y",),
    )
    relation = memory.resolve(
        source_intervention="action:x",
        target_observation=("obs:y",),
    )
    assert relation.supported is False
    assert relation.reason == "insufficient-independent-support"


def test_recurrent_pattern_across_independent_episodes_becomes_supported():
    memory = InteragentCausalMemory()
    for episode in ("E1", "E2"):
        memory.observe(
            episode_id=episode,
            source_agent="A",
            source_intervention="action:x",
            target_agent="B",
            target_observation=("obs:y",),
        )
    relation = memory.resolve(
        source_intervention="action:x",
        target_observation=("obs:y",),
    )
    assert relation.supported is True
    assert relation.independent_episodes == ("E1", "E2")


def test_duplicate_same_episode_does_not_fake_independent_support():
    memory = InteragentCausalMemory()
    for _ in range(3):
        memory.observe(
            episode_id="E1",
            source_agent="A",
            source_intervention="action:x",
            target_agent="B",
            target_observation=("obs:y",),
        )
    relation = memory.resolve(
        source_intervention="action:x",
        target_observation=("obs:y",),
    )
    assert relation.supported is False
    assert relation.independent_episodes == ("E1",)


def test_competing_target_observations_remain_separate_hypotheses():
    memory = InteragentCausalMemory()
    for episode, observation in (("E1", "obs:y"), ("E2", "obs:y"), ("E3", "obs:z"), ("E4", "obs:z")):
        memory.observe(
            episode_id=episode,
            source_agent="A",
            source_intervention="action:x",
            target_agent="B",
            target_observation=(observation,),
        )
    y = memory.resolve(source_intervention="action:x", target_observation=("obs:y",))
    z = memory.resolve(source_intervention="action:x", target_observation=("obs:z",))
    assert y.supported is True
    assert z.supported is True


def test_source_target_identity_is_rejected():
    memory = InteragentCausalMemory()
    try:
        memory.observe(
            episode_id="E1",
            source_agent="A",
            source_intervention="action:x",
            target_agent="A",
            target_observation=("obs:y",),
        )
    except ValueError as exc:
        assert "distinct agents" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_restart_preserves_supported_relation_deterministically():
    memory = InteragentCausalMemory()
    for episode in ("E2", "E1"):
        memory.observe(
            episode_id=episode,
            source_agent="A",
            source_intervention="action:x",
            target_agent="B",
            target_observation=("obs:y",),
        )
    restored = InteragentCausalMemory.restore(memory.snapshot())
    assert memory.resolve(source_intervention="action:x", target_observation=("obs:y",)) == restored.resolve(
        source_intervention="action:x",
        target_observation=("obs:y",),
    )
