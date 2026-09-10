from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.dynamic_branch_state_v2 import DynamicBranchStateResolver
from memoria_resolutiva.trajectory_recovery_v2 import TrajectoryRecoveryResolver


def test_exhaustion_can_reopen_retrieval_from_new_observation() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    memory.ingest("zeta eta theta")
    dynamic = DynamicBranchStateResolver(memory)
    state = dynamic.begin("alpha beta")

    result = TrajectoryRecoveryResolver(memory).recover_text(state, "zeta")
    assert result.recovered is True
    assert result.recovered_state is not None
    assert result.recovered_state.exhausted is False


def test_recovery_does_not_stitch_old_and_new_occurrences() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a hub x")
    memory.ingest("b hub y")
    dynamic = DynamicBranchStateResolver(memory)
    state = dynamic.begin("a hub")

    result = TrajectoryRecoveryResolver(memory).recover_text(state, "b hub")
    assert result.recovered is True
    assert result.recovered_state is not None
    remaining = {surface for branch in result.recovered_state.active for surface in branch.remaining_surfaces}
    assert "y" in remaining


def test_compatible_observation_updates_without_recovery() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma delta")
    state = DynamicBranchStateResolver(memory).begin("alpha beta")

    result = TrajectoryRecoveryResolver(memory).recover_text(state, "gamma")
    assert result.recovered is False
    assert result.recovered_state is not None
    assert result.recovered_state.exhausted is False


def test_unknown_observation_can_remain_unresolved() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    state = DynamicBranchStateResolver(memory).begin("alpha beta")

    result = TrajectoryRecoveryResolver(memory).recover_text(state, "never-seen-symbol")
    assert result.recovered is False
    assert result.recovered_state is None


def test_recovery_is_read_only() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    memory.ingest("zeta eta theta")
    before = memory.snapshot()
    state = DynamicBranchStateResolver(memory).begin("alpha beta")
    TrajectoryRecoveryResolver(memory).recover_text(state, "zeta")
    assert memory.snapshot() == before


def test_recovery_is_deterministic_after_restart() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma")
    memory.ingest("zeta eta theta")
    first_state = DynamicBranchStateResolver(memory).begin("alpha beta")
    first = TrajectoryRecoveryResolver(memory).recover_text(first_state, "zeta")

    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    second_state = DynamicBranchStateResolver(restored).begin("alpha beta")
    second = TrajectoryRecoveryResolver(restored).recover_text(second_state, "zeta")
    assert first == second
