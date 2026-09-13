from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.branch_evolution_v2 import BranchEvolutionSession


def test_shared_prefix_keeps_multiple_branches_alive() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma delta")
    memory.ingest("alpha beta gamma omega")

    session = BranchEvolutionSession(memory, "alpha beta")
    state = session.observe_text("gamma")

    assert state.ambiguous is True
    assert state.collapsed is None
    assert len(state.active) == 2


def test_later_observation_collapses_only_at_real_divergence() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("alpha beta gamma delta")
    memory.ingest("alpha beta gamma omega")

    session = BranchEvolutionSession(memory, "alpha beta")
    session.observe_text("gamma")
    state = session.observe_text("delta")

    assert state.ambiguous is False
    assert state.collapsed is not None
    assert state.collapsed.path.continuation_surfaces[-1] == "delta"


def test_contradictory_observation_exhausts_without_creating_fact() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("a b c")
    memory.ingest("a b d")
    before = memory.snapshot()

    session = BranchEvolutionSession(memory, "a b")
    state = session.observe_text("z")

    assert state.exhausted is True
    assert state.collapsed is None
    assert memory.snapshot() == before


def test_observation_is_read_only() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato e Lotus")
    before = memory.snapshot()

    session = BranchEvolutionSession(memory, "meu gato")
    session.observe_text("e")

    assert memory.snapshot() == before


def test_cold_restart_reproduces_same_evolution() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("x y z q")
    memory.ingest("x y z r")

    first = BranchEvolutionSession(memory, "x y")
    state1 = first.observe_text("z")

    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    second = BranchEvolutionSession(restored, "x y")
    state2 = second.observe_text("z")

    assert state1 == state2


def test_address_stream_observation_collapses_immediate_repeats() -> None:
    memory = AddressTrajectoryMemory()
    session = BranchEvolutionSession(memory, "")

    state = session.observe_addresses(("sensor:C", "sensor:C"))
    assert state.observations == (("sensor:C",),)


def test_immediate_loop_cache_persists_across_observation_calls() -> None:
    memory = AddressTrajectoryMemory()
    session = BranchEvolutionSession(memory, "")

    first = session.observe_addresses(("sensor:C",))
    second = session.observe_addresses(("sensor:C",))

    assert first.observations == (("sensor:C",),)
    assert second.observations == (("sensor:C",),)
