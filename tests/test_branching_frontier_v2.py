from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.branching_frontier_v2 import BranchingFrontierResolver


def test_equal_structural_branches_remain_ambiguous() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    memory.ingest("alpha beta omega")
    resolver = BranchingFrontierResolver(memory)

    result = resolver.resolve("alpha beta")
    assert result.ambiguous is True
    assert result.collapsed is None
    assert {item.surface for item in result.hypotheses[:2]} == {"gamma", "omega"}


def test_shared_first_continuation_is_one_branch_until_real_divergence() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato e Lotus")
    memory.ingest("meu gato e Vibe")
    resolver = BranchingFrontierResolver(memory)

    result = resolver.resolve("meu gato")
    assert result.hypotheses
    assert result.hypotheses[0].surface == "e"
    assert result.hypotheses[0].candidate_count >= 2


def test_independent_trajectories_can_support_same_branch_address() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    memory.ingest("alpha beta gamma delta")
    memory.ingest("alpha beta omega")
    resolver = BranchingFrontierResolver(memory)

    result = resolver.resolve("alpha beta")
    assert result.hypotheses
    gamma = next(item for item in result.hypotheses if item.surface == "gamma")
    assert gamma.candidate_count >= 2


def test_query_is_read_only() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    before = memory.snapshot()
    BranchingFrontierResolver(memory).resolve("a b")
    assert memory.snapshot() == before


def test_cold_restart_preserves_branch_resolution() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("x y z")
    memory.ingest("x y q")
    first = BranchingFrontierResolver(memory).resolve("x y")
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    second = BranchingFrontierResolver(restored).resolve("x y")
    assert first == second
