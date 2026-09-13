from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.dynamic_branch_state_v2 import DynamicBranchStateResolver


def test_recovery_opens_new_episode_without_merging_old_and_new_trajectory() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("x y z")
    resolver = DynamicBranchStateResolver(memory)

    old_state = resolver.begin("a b")
    exhausted = resolver.observe_text(old_state, "x")
    assert exhausted.exhausted is True

    recovery = resolver.recover_text(exhausted, "x")

    assert recovery.previous.query == "a b"
    assert recovery.previous.exhausted is True
    assert recovery.recovered.query == "x"
    assert recovery.recovered_any is True
    assert recovery.recovered.active[0].trajectory_ids == ("AT2",)
    assert recovery.recovered.active[0].remaining_surfaces == ("y", "z")

    # Recovery may reorient retrieval, but it must not synthesize a new stored
    # path such as a -> b -> x -> y -> z.
    assert len(memory.snapshot()) == 2
    assert memory.snapshot()[0].surfaces == ("a", "b", "c")
    assert memory.snapshot()[1].surfaces == ("x", "y", "z")


def test_unknown_recovery_can_fail_open_without_creating_memory() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    resolver = DynamicBranchStateResolver(memory)

    state = resolver.begin("a b")
    exhausted = resolver.observe_text(state, "unknown")
    assert exhausted.exhausted is True

    before = memory.snapshot()
    recovery = resolver.recover_text(exhausted, "unknown")

    assert recovery.recovered_any is False
    assert recovery.recovered.exhausted is True
    assert recovery.recovered.active == ()
    assert memory.snapshot() == before


def test_recovery_address_stream_is_modality_agnostic() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("s:A", "s:B", "s:C"), surfaces=("A", "B", "C"))
    memory.ingest_address_stream(("s:X", "s:Y", "s:Z"), surfaces=("X", "Y", "Z"))
    resolver = DynamicBranchStateResolver(memory)

    state = resolver.begin_addresses(("s:A", "s:B"))
    exhausted = resolver.observe_addresses(state, ("s:X",))
    assert exhausted.exhausted is True

    recovery = resolver.recover_addresses(exhausted, ("s:X",), query_label="sensor-recovery")
    assert recovery.recovered_any is True
    assert recovery.recovered.active[0].trajectory_ids == ("AT2",)
    assert recovery.recovered.active[0].remaining_addresses == ("s:Y", "s:Z")
