from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.dynamic_branch_state_v2 import DynamicBranchStateResolver


def _addr(memory: AddressTrajectoryMemory, text: str) -> str:
    return memory.decompose(text)[0].address


def _exhaust_with(memory: AddressTrajectoryMemory, query: str, unexpected: str):
    resolver = DynamicBranchStateResolver(memory)
    state = resolver.begin(query)
    exhausted = resolver.observe_text(state, unexpected)
    assert exhausted.exhausted is True
    return resolver, exhausted


def test_exhaustion_reseeds_into_another_known_trajectory() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("x y z")
    resolver, exhausted = _exhaust_with(memory, "a b", "x")

    recovery = resolver.recover_text(exhausted, "x")
    assert recovery.recovered_any is True
    assert recovery.recovered.active[0].remaining_surfaces == ("y", "z")


def test_unknown_observation_remains_unresolved() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    resolver, exhausted = _exhaust_with(memory, "a b", "never-seen")

    recovery = resolver.recover_text(exhausted, "never-seen")
    assert recovery.recovered_any is False
    assert recovery.recovered.exhausted is True


def test_recovery_never_mutates_persistent_memory() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("x y z")
    resolver, exhausted = _exhaust_with(memory, "a b", "x")
    before = memory.snapshot()

    resolver.recover_text(exhausted, "x")
    assert memory.snapshot() == before


def test_recovery_does_not_create_false_global_edge() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a hub c")
    memory.ingest("x hub y")
    resolver, exhausted = _exhaust_with(memory, "a hub", "x")
    before = memory.snapshot()

    recovery = resolver.recover_text(exhausted, "x hub")
    assert recovery.recovered_any is True
    remaining = {
        branch.remaining_surfaces
        for branch in recovery.recovered.active
    }
    assert ("y",) in remaining
    assert ("c",) not in remaining
    assert memory.snapshot() == before


def test_cold_restart_keeps_recovery_deterministic() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("x y z")
    resolver, exhausted = _exhaust_with(memory, "a b", "x")
    first = resolver.recover_text(exhausted, "x")

    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    second = DynamicBranchStateResolver(restored).recover_text(exhausted, "x")
    assert first == second


def test_multiple_consecutive_recoveries_can_reorient_again() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("x y z")
    memory.ingest("m n o")
    resolver, exhausted = _exhaust_with(memory, "a b", "x")

    first = resolver.recover_text(exhausted, "x")
    assert first.recovered_any is True
    second_exhausted = resolver.observe_text(first.recovered, "m")
    assert second_exhausted.exhausted is True

    second = resolver.recover_text(second_exhausted, "m")
    assert second.recovered_any is True
    assert second.recovered.active[0].remaining_surfaces == ("n", "o")


def test_hyperdense_address_does_not_force_arbitrary_reseed() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a hub c")
    memory.ingest("b hub d")
    memory.ingest("e hub f")
    memory.ingest("x hub y")
    resolver, exhausted = _exhaust_with(memory, "a hub", "x")

    recovery = resolver.recover_text(exhausted, "x hub")
    assert recovery.recovered_any is True
    assert len(recovery.recovered.active) == 1
    assert recovery.recovered.active[0].remaining_surfaces == ("y",)


def test_multimodal_address_stream_can_recover() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(
        ("sensor:A", "sensor:B", "sensor:C"),
        surfaces=("A", "B", "C"),
        provenance="sensor-one",
    )
    memory.ingest_address_stream(
        ("audio:X", "audio:Y", "audio:Z"),
        surfaces=("X", "Y", "Z"),
        provenance="audio-one",
    )
    resolver = DynamicBranchStateResolver(memory)
    state = resolver.begin_addresses(("sensor:A", "sensor:B"))
    exhausted = resolver.observe_addresses(state, ("audio:X",))
    assert exhausted.exhausted is True

    recovery = resolver.recover_addresses(exhausted, ("audio:X",))
    assert recovery.recovered_any is True
    assert recovery.recovered.active[0].remaining_addresses == ("audio:Y", "audio:Z")


def test_recovery_can_open_a_new_branching_frontier() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("x y left")
    memory.ingest("x y right")
    resolver, exhausted = _exhaust_with(memory, "a b", "x")

    recovery = resolver.recover_text(exhausted, "x y")
    assert recovery.recovered_any is True
    assert recovery.recovered.ambiguous is True
    assert {
        branch.remaining_surfaces[0]
        for branch in recovery.recovered.active
    } == {"left", "right"}


def test_recovery_can_return_to_trajectory_discarded_in_prior_context() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("a b d")
    memory.ingest("c q r")
    resolver = DynamicBranchStateResolver(memory)

    state = resolver.begin("a b")
    c = _addr(memory, "c")
    state = resolver.observe_address(state, c)
    assert state.exhausted is False
    assert state.ambiguous is False

    # Move to another known region; the prior competing a-b-d trajectory is no
    # longer active in this context, but remains stored.
    q = _addr(memory, "q")
    state = resolver.observe_address(state, q)
    assert state.exhausted is True

    d = _addr(memory, "d")
    recovery = resolver.recover_addresses(state, (_addr(memory, "a"), _addr(memory, "b")))
    assert recovery.recovered_any is True
    futures = {
        branch.remaining_addresses[0]
        for branch in recovery.recovered.active
    }
    assert c in futures
    assert d in futures
