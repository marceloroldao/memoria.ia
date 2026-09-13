from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.address_composition_v2 import AddressCompositionEngine
from memoria_resolutiva.composed_convergence_v2 import ComposedAddressConvergenceResolver


def _memory() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato dorme aqui")
    memory.ingest("meu gato come agora")
    memory.ingest("irmao de meu gato e Lotus")
    memory.ingest("meu carro e azul")
    return memory


def test_composed_resolver_keeps_correct_lotus_candidate() -> None:
    memory = _memory()
    resolver = ComposedAddressConvergenceResolver(memory)
    matches = resolver.resolve("qual e irmao de meu gato")
    assert matches
    assert matches[0].terminal_surface == "lotus"


def test_composition_can_shorten_stored_trajectory() -> None:
    memory = _memory()
    engine = AddressCompositionEngine(memory, min_size=2, max_size=3, min_occurrences=2)
    resolver = ComposedAddressConvergenceResolver(memory, composition_engine=engine)
    matches = resolver.resolve("meu gato")
    target = next(match for match in matches if match.terminal_surface == "aqui")
    assert target.composed_length < target.atomic_length


def test_repeated_query_over_composed_view_is_read_only() -> None:
    memory = _memory()
    resolver = ComposedAddressConvergenceResolver(memory)
    before = memory.snapshot()
    first = resolver.resolve("qual e irmao de meu gato")
    second = resolver.resolve("qual e irmao de meu gato")
    after = memory.snapshot()
    assert first == second
    assert before == after


def test_composed_resolution_is_restart_deterministic() -> None:
    memory = _memory()
    query = "qual e irmao de meu gato"
    before = ComposedAddressConvergenceResolver(memory).resolve(query)
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    after = ComposedAddressConvergenceResolver(restored).resolve(query)
    assert before == after


def test_composition_does_not_require_text_modality() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("audio:A", "audio:B", "audio:C"), provenance="one")
    memory.ingest_address_stream(("audio:A", "audio:B", "audio:D"), provenance="two")
    engine = AddressCompositionEngine(memory)
    catalogue = engine.discover()
    assert any(item.children == ("audio:A", "audio:B") for item in catalogue)
