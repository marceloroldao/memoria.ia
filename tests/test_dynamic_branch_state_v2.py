from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.dynamic_branch_state_v2 import DynamicBranchStateResolver


def test_new_observation_eliminates_only_incompatible_branch() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma delta")
    memory.ingest("alpha beta gamma omega")
    resolver = DynamicBranchStateResolver(memory)

    state = resolver.begin("alpha beta", max_steps=4)
    assert state.ambiguous is True
    gamma = memory.decompose("gamma")[0].address
    state = resolver.observe_address(state, gamma)
    assert state.ambiguous is True

    delta = memory.decompose("delta")[0].address
    state = resolver.observe_address(state, delta)
    assert state.exhausted is False
    assert state.ambiguous is False
    assert len(state.active) == 1
    assert any(tid in state.eliminated_trajectory_ids for tid in ("AT1", "AT2"))


def test_underlying_memory_is_never_mutated_or_marked_false() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("a b d")
    before = memory.snapshot()
    resolver = DynamicBranchStateResolver(memory)
    state = resolver.begin("a b")
    c = memory.decompose("c")[0].address
    state = resolver.observe_address(state, c)
    assert memory.snapshot() == before
    assert state.eliminated_trajectory_ids


def test_unexpected_observation_can_exhaust_ephemeral_state_without_deleting_memory() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("a b d")
    resolver = DynamicBranchStateResolver(memory)
    state = resolver.begin("a b")
    unknown = memory.decompose("z")[0].address
    state = resolver.observe_address(state, unknown)
    assert state.exhausted is True
    assert state.active == ()
    assert len(memory.snapshot()) == 2


def test_observe_text_consumes_multiple_steps_in_order() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("start mid left end")
    memory.ingest("start mid right end")
    resolver = DynamicBranchStateResolver(memory)
    state = resolver.begin("start")
    state = resolver.observe_text(state, "mid left")
    assert state.exhausted is False
    assert state.ambiguous is False
    assert len(state.active) == 1
    assert state.active[0].consumed_steps == 2


def test_cold_restart_same_initial_dynamic_state() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("x y p q")
    memory.ingest("x y r s")
    first = DynamicBranchStateResolver(memory).begin("x y")
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    second = DynamicBranchStateResolver(restored).begin("x y")
    assert first == second
