from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.topological_density_v2 import (
    LoopRejectingAddressCache,
    TopologicalDensityEngine,
    collapse_immediate_loops,
)


def test_density_emerges_from_topology_not_vocabulary() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("de gato para casa")
    memory.ingest("de carro para rua")
    memory.ingest("de amigo para escola")
    memory.ingest("de audio para texto")

    engine = TopologicalDensityEngine(memory)
    de_profile = engine.profile_for_surface("de")
    assert de_profile is not None
    assert de_profile.trajectory_count == 4
    assert de_profile.successor_count == 4

    gato_profile = engine.profile_for_surface("gato")
    assert gato_profile is not None
    assert de_profile.topological_key > gato_profile.topological_key


def test_immediate_same_address_does_not_advance_cache() -> None:
    memory = AddressTrajectoryMemory()
    address = memory.decompose("de")[0].address
    cache = LoopRejectingAddressCache()

    first = cache.push(address)
    second = cache.push(address)
    third = cache.push(address)

    assert first.accepted is True
    assert second.accepted is False
    assert third.accepted is False
    assert cache.current == address
    assert cache.accepted_count == 1
    assert cache.rejected_loop_count == 2


def test_different_address_releases_cache_and_same_value_can_later_recur() -> None:
    memory = AddressTrajectoryMemory()
    de = memory.decompose("de")[0].address
    gato = memory.decompose("gato")[0].address
    cache = LoopRejectingAddressCache()

    assert cache.push(de).accepted
    assert not cache.push(de).accepted
    assert cache.push(gato).accepted
    assert cache.push(de).accepted

    assert cache.accepted_count == 3
    assert cache.rejected_loop_count == 1


def test_repeated_stopword_like_stream_collapses_without_stopword_list() -> None:
    memory = AddressTrajectoryMemory()
    accepted = collapse_immediate_loops(memory, "de de de de de de de de de de de")
    assert len(accepted) == 1


def test_loop_rejection_is_generic_for_any_symbol_not_just_language_stopwords() -> None:
    memory = AddressTrajectoryMemory()
    repeated_de = collapse_immediate_loops(memory, "de de de de")
    repeated_x = collapse_immediate_loops(memory, "x x x x")
    repeated_sensor = collapse_immediate_loops(memory, "sensor42 sensor42 sensor42")
    assert len(repeated_de) == len(repeated_x) == len(repeated_sensor) == 1


def test_density_engine_does_not_remove_hyperconnected_nodes() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("de gato para casa")
    memory.ingest("de carro para rua")
    memory.ingest("de audio para texto")

    engine = TopologicalDensityEngine(memory)
    densest = engine.densest(limit=10)
    surfaces = {item.surface for item in densest}
    assert "de" in surfaces


def test_query_like_repetition_cannot_create_extra_memory() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("de gato para casa")
    before = memory.snapshot()
    collapse_immediate_loops(memory, "de de de de de")
    after = memory.snapshot()
    assert before == after
