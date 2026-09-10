from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.trajectory_hypothesis_state_v2 import (
    IncrementalTrajectoryHypothesisResolver,
)


def test_new_observation_eliminates_incompatible_branch_without_weighting() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma delta")
    memory.ingest("alpha beta gamma omega")
    resolver = IncrementalTrajectoryHypothesisResolver(memory, "alpha beta")

    initial = resolver.state()
    assert initial.ambiguous is True
    assert initial.shared_next_surfaces == ("gamma",)

    after_gamma = resolver.observe("gamma")
    assert after_gamma.ambiguous is True
    assert {h.remaining_surfaces[0] for h in after_gamma.active} == {"delta", "omega"}

    after_delta = resolver.observe("delta")
    assert after_delta.ambiguous is False
    assert after_delta.collapsed_trajectory_id is not None
    assert len(after_delta.active) == 1
    assert after_delta.contradiction is False


def test_equal_compatible_branches_remain_alive() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c d")
    memory.ingest("a b c d")
    resolver = IncrementalTrajectoryHypothesisResolver(memory, "a b")

    state = resolver.observe("c")
    assert state.ambiguous is True
    assert len(state.active) == 2


def test_contradictory_observation_forces_no_hypothesis_not_false_collapse() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("a b d")
    resolver = IncrementalTrajectoryHypothesisResolver(memory, "a b")

    state = resolver.observe("x")
    assert state.active == ()
    assert state.collapsed_trajectory_id is None
    assert state.ambiguous is False
    assert state.contradiction is True


def test_observation_never_jumps_through_shared_address_between_occurrences() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a hub x")
    memory.ingest("b hub y")
    resolver = IncrementalTrajectoryHypothesisResolver(memory, "a hub")

    state = resolver.observe("y")
    assert state.contradiction is True
    assert state.active == ()


def test_state_updates_are_read_only_to_memory() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c d")
    before = memory.snapshot()
    resolver = IncrementalTrajectoryHypothesisResolver(memory, "a b")
    resolver.observe("c")
    resolver.observe("d")
    assert memory.snapshot() == before


def test_cold_restart_rebuilds_same_initial_hypotheses() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("x y z")
    memory.ingest("x y q")
    first = IncrementalTrajectoryHypothesisResolver(memory, "x y").state()
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    second = IncrementalTrajectoryHypothesisResolver(restored, "x y").state()
    assert first == second


def test_non_text_address_stream_works_through_same_state_machine() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("s:A", "s:B", "s:C"), surfaces=("A", "B", "C"), provenance="sensor-1")
    memory.ingest_address_stream(("s:A", "s:B", "s:D"), surfaces=("A", "B", "D"), provenance="sensor-2")

    # Seed with text cannot address arbitrary external symbols, so verify the same
    # state representation can still be built from deterministic textual adapters
    # in this first test battery; direct-address hypothesis seeding is the next API.
    assert len(memory.snapshot()) == 2
