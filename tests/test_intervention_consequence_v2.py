from memoria_resolutiva.intervention_consequence_v2 import InterventionConsequenceMemory


def _memory():
    memory = InterventionConsequenceMemory()
    memory.ingest_episode(("state:near-fire",), "action:approach", ("sensor:warmer",), ("state:nearer-fire",))
    memory.ingest_episode(("state:near-fire",), "action:approach", ("sensor:warmer",), ("state:nearer-fire",))
    return memory


def test_supported_state_action_resolves_consequence():
    memory = _memory()
    result = memory.resolve(("state:near-fire",), "action:approach")
    assert result.resolved is True
    assert result.ambiguous is False
    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].consequence_addresses == ("sensor:warmer",)
    assert result.hypotheses[0].next_state_addresses == ("state:nearer-fire",)


def test_single_episode_is_not_enough_by_default():
    memory = InterventionConsequenceMemory()
    memory.ingest_episode(("s",), "a", ("c",), ("n",))
    result = memory.resolve(("s",), "a")
    assert result.resolved is False
    assert result.reason == "insufficient-supported-consequence"


def test_competing_repeated_consequences_remain_ambiguous():
    memory = _memory()
    memory.ingest_episode(("state:near-fire",), "action:approach", ("sensor:unchanged",), ("state:near-fire",))
    memory.ingest_episode(("state:near-fire",), "action:approach", ("sensor:unchanged",), ("state:near-fire",))
    result = memory.resolve(("state:near-fire",), "action:approach")
    assert result.resolved is False
    assert result.ambiguous is True
    assert len(result.hypotheses) == 2


def test_same_action_in_different_state_does_not_transfer_consequence():
    memory = _memory()
    memory.ingest_episode(("state:far-fire",), "action:approach", ("sensor:slightly-warmer",), ("state:closer",))
    memory.ingest_episode(("state:far-fire",), "action:approach", ("sensor:slightly-warmer",), ("state:closer",))
    near = memory.resolve(("state:near-fire",), "action:approach")
    far = memory.resolve(("state:far-fire",), "action:approach")
    assert near.hypotheses[0].consequence_addresses == ("sensor:warmer",)
    assert far.hypotheses[0].consequence_addresses == ("sensor:slightly-warmer",)


def test_query_is_read_only_and_restart_deterministic():
    memory = _memory()
    before = memory.snapshot()
    result1 = memory.resolve(("state:near-fire",), "action:approach")
    restored = InterventionConsequenceMemory.restore(before)
    result2 = restored.resolve(("state:near-fire",), "action:approach")
    assert result1 == result2
    assert memory.snapshot() == before


def test_immediate_duplicates_are_collapsed_multimodally():
    memory = InterventionConsequenceMemory()
    episode = memory.ingest_episode(("s", "s", "x"), "a", ("c", "c"), ("n", "n"))
    assert episode.state_addresses == ("s", "x")
    assert episode.consequence_addresses == ("c",)
    assert episode.next_state_addresses == ("n",)
