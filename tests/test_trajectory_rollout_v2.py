from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.trajectory_rollout_v2 import TrajectoryRolloutResolver


def test_rollout_exposes_shared_prefix_until_real_divergence() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma delta")
    memory.ingest("alpha beta gamma omega")
    resolver = TrajectoryRolloutResolver(memory)

    result = resolver.resolve("alpha beta", max_steps=4)
    assert result.shared_prefix_surfaces == ("gamma",)
    assert result.divergence_index == 1
    tails = {tuple(path.continuation_surfaces) for path in result.branches}
    assert ("gamma", "delta") in tails
    assert ("gamma", "omega") in tails


def test_identical_future_sequences_are_aggregated() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma delta")
    memory.ingest("alpha beta gamma delta")
    resolver = TrajectoryRolloutResolver(memory)

    result = resolver.resolve("alpha beta", max_steps=4)
    assert len(result.branches) == 1
    assert len(result.branches[0].trajectory_ids) == 2
    assert result.shared_prefix_surfaces == ("gamma", "delta")
    assert result.divergence_index is None


def test_rollout_does_not_jump_between_occurrence_trajectories() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a hub x")
    memory.ingest("b hub y")
    resolver = TrajectoryRolloutResolver(memory)

    result = resolver.resolve("a hub", max_steps=3)
    surfaces = {tuple(path.continuation_surfaces) for path in result.branches}
    assert ("x",) in surfaces
    assert ("y",) not in surfaces


def test_rollout_respects_max_steps() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c d e f")
    result = TrajectoryRolloutResolver(memory).resolve("a b", max_steps=2)
    assert result.branches
    assert result.branches[0].continuation_surfaces == ("c", "d")


def test_rollout_query_is_read_only() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c d")
    before = memory.snapshot()
    TrajectoryRolloutResolver(memory).resolve("a b")
    assert memory.snapshot() == before


def test_rollout_is_cold_restart_deterministic() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("x y z q")
    memory.ingest("x y z r")
    first = TrajectoryRolloutResolver(memory).resolve("x y")
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    second = TrajectoryRolloutResolver(restored).resolve("x y")
    assert first == second
