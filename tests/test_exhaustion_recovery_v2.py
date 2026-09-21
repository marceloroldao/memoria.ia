from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.dynamic_branch_state_v2 import DynamicBranchStateResolver
from memoria_resolutiva.exhaustion_recovery_v2 import ExhaustionRecoveryResolver


def _address(memory: AddressTrajectoryMemory, text: str) -> str:
    return memory.decompose(text)[0].address


def test_exhausted_state_reanchors_on_observed_suffix() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("z q r")
    dynamic = DynamicBranchStateResolver(memory)
    state = dynamic.begin("a b")
    state = dynamic.observe_address(state, _address(memory, "z"))
    assert state.exhausted is True

    result = ExhaustionRecoveryResolver(memory).recover(state)
    assert result.recovered is True
    assert result.recovered_query_addresses == (_address(memory, "z"),)
    assert result.recovery.branches
    assert result.recovery.branches[0].continuation_surfaces[0] == "q"


def test_longest_observed_suffix_is_preferred() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("x y p")
    memory.ingest("y q")
    dynamic = DynamicBranchStateResolver(memory)
    state = dynamic.begin("a b")
    state = dynamic.observe_address(state, _address(memory, "x"))
    assert state.exhausted is True
    # extend the observed exhausted state deterministically
    state = state.__class__(
        query=state.query,
        observed_addresses=state.observed_addresses + (_address(memory, "y"),),
        active=state.active,
        eliminated_trajectory_ids=state.eliminated_trajectory_ids,
        exhausted=True,
        ambiguous=False,
    )

    result = ExhaustionRecoveryResolver(memory).recover(state)
    assert result.recovered is True
    assert result.recovered_query_addresses == (_address(memory, "x"), _address(memory, "y"))
    assert result.recovery.branches[0].continuation_surfaces[0] == "p"


def test_recovery_does_not_invent_global_hub_jump() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a hub x")
    memory.ingest("b hub y")
    dynamic = DynamicBranchStateResolver(memory)
    state = dynamic.begin("a")
    state = dynamic.observe_address(state, _address(memory, "b"))
    assert state.exhausted is True

    result = ExhaustionRecoveryResolver(memory).recover(state)
    assert result.recovered is True
    surfaces = [path.continuation_surfaces for path in result.recovery.branches]
    assert ("hub", "y") in surfaces
    assert ("hub", "x") not in surfaces


def test_unseen_observation_remains_unrecovered() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    dynamic = DynamicBranchStateResolver(memory)
    state = dynamic.begin("a b")
    state = dynamic.observe_address(state, _address(memory, "never-seen"))
    result = ExhaustionRecoveryResolver(memory).recover(state)
    assert result.recovered is False
    assert result.recovery.exhausted is True


def test_recovery_is_read_only_and_restart_deterministic() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("z q r")
    dynamic = DynamicBranchStateResolver(memory)
    state = dynamic.begin("a b")
    state = dynamic.observe_address(state, _address(memory, "z"))
    before = memory.snapshot()
    first = ExhaustionRecoveryResolver(memory).recover(state)
    assert memory.snapshot() == before

    restored = AddressTrajectoryMemory.restore(before)
    second = ExhaustionRecoveryResolver(restored).recover(state)
    assert first == second
