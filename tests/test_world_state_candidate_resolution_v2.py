from memoria_resolutiva.intervention_consequence_v2 import InterventionConsequenceMemory
from memoria_resolutiva.world_state_candidate_resolution_v2 import (
    WorldStateCandidate,
    resolve_world_state_candidates,
)


def _trained_memory() -> InterventionConsequenceMemory:
    memory = InterventionConsequenceMemory()
    # Same literal-free geometry across independent episodes:
    # [S0,S1] + novel action -> [N0] -> [S0,N0]
    memory.ingest_episode(("train:a", "train:b"), "train:act", ("train:x",), ("train:a", "train:x"))
    memory.ingest_episode(("other:a", "other:b"), "other:act", ("other:x",), ("other:a", "other:x"))
    return memory


def test_selects_single_concrete_candidate_from_world_state():
    memory = _trained_memory()
    candidates = (
        WorldStateCandidate("good", ("live:new",), ("live:a", "live:new")),
        WorldStateCandidate("bad", ("live:a",), ("live:a", "live:b")),
    )
    result = resolve_world_state_candidates(
        memory,
        ("live:a", "live:b"),
        "live:act",
        candidates,
    )
    assert result.resolved is True
    assert result.ambiguous is False
    assert result.resolved_candidate is not None
    assert result.resolved_candidate.candidate_id == "good"


def test_multiple_structurally_valid_candidates_remain_ambiguous():
    memory = _trained_memory()
    candidates = (
        WorldStateCandidate("c1", ("live:x",), ("live:a", "live:x")),
        WorldStateCandidate("c2", ("live:y",), ("live:a", "live:y")),
    )
    result = resolve_world_state_candidates(
        memory,
        ("live:a", "live:b"),
        "live:act",
        candidates,
    )
    assert result.resolved is False
    assert result.ambiguous is True
    assert result.resolved_candidate is None
    assert tuple(match.candidate.candidate_id for match in result.matches) == ("c1", "c2")


def test_no_compatible_candidate_does_not_invent_a_future():
    memory = _trained_memory()
    result = resolve_world_state_candidates(
        memory,
        ("live:a", "live:b"),
        "live:act",
        (WorldStateCandidate("bad", ("live:a",), ("live:a", "live:b")),),
    )
    assert result.resolved is False
    assert result.ambiguous is False
    assert result.resolved_candidate is None
    assert result.reason == "no-compatible-world-candidate"


def test_insufficient_training_support_fails_closed():
    memory = InterventionConsequenceMemory()
    memory.ingest_episode(("a", "b"), "act", ("x",), ("a", "x"))
    result = resolve_world_state_candidates(
        memory,
        ("live:a", "live:b"),
        "live:act",
        (WorldStateCandidate("candidate", ("live:x",), ("live:a", "live:x")),),
    )
    assert result.resolved is False
    assert result.reason == "no-supported-structural-pattern"


def test_candidate_resolution_is_read_only_and_restart_deterministic():
    memory = _trained_memory()
    before = memory.snapshot()
    candidates = (WorldStateCandidate("good", ("live:new",), ("live:a", "live:new")),)
    first = resolve_world_state_candidates(memory, ("live:a", "live:b"), "live:act", candidates)
    assert memory.snapshot() == before

    restored = InterventionConsequenceMemory.restore(before)
    second = resolve_world_state_candidates(restored, ("live:a", "live:b"), "live:act", candidates)
    assert first == second


def test_same_candidates_under_different_state_geometry_are_not_forced():
    memory = _trained_memory()
    candidate = WorldStateCandidate("candidate", ("live:new",), ("live:a", "live:new"))
    result = resolve_world_state_candidates(
        memory,
        ("live:a", "live:b", "live:c"),
        "live:act",
        (candidate,),
    )
    assert result.resolved is False
    assert result.reason == "no-supported-structural-pattern"
