from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.address_composition_v2 import AddressCompositionEngine


def test_repeated_sequence_gains_stable_address_without_semantics() -> None:
    memory = AddressTrajectoryMemory()
    t1 = memory.ingest("meu gato dorme aqui")
    t2 = memory.ingest("meu gato come agora")
    engine = AddressCompositionEngine(memory, min_size=2, max_size=3, min_occurrences=2)
    discovered = engine.discover()
    pair = next(item for item in discovered if item.children == t1.addresses[:2])
    assert pair.children == t2.addresses[:2]
    assert pair.occurrences == 2
    assert pair.trajectory_count == 2
    assert pair.address.startswith("ac2:")


def test_composition_address_is_deterministic_across_restart() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato dorme")
    memory.ingest("meu gato corre")
    first = AddressCompositionEngine(memory).discover()
    restored = AddressTrajectoryMemory.restore(memory.snapshot())
    second = AddressCompositionEngine(restored).discover()
    assert first == second


def test_composition_is_derived_view_and_does_not_mutate_raw_memory() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("meu gato dorme")
    memory.ingest("meu gato corre")
    before = memory.snapshot()
    engine = AddressCompositionEngine(memory)
    composed = engine.compose_text("meu gato pula")
    after = memory.snapshot()
    assert before == after
    assert len(composed) == 2
    assert composed[0].startswith("ac2:")


def test_longest_recurring_composition_wins_without_weight() -> None:
    memory = AddressTrajectoryMemory()
    t1 = memory.ingest("a b c x")
    memory.ingest("a b c y")
    engine = AddressCompositionEngine(memory, min_size=2, max_size=3, min_occurrences=2)
    composed = engine.compose_addresses(t1.addresses)
    # [a,b,c] is recurrent and must collapse before the shorter [a,b] pair.
    assert len(composed) == 2
    assert composed[0].startswith("ac2:")


def test_immediate_loop_rejection_happens_before_composition_discovery() -> None:
    memory = AddressTrajectoryMemory()
    t1 = memory.ingest("de de gato")
    t2 = memory.ingest("de gato")
    assert t1.addresses == t2.addresses
    engine = AddressCompositionEngine(memory)
    discovered = engine.discover()
    pair = next(item for item in discovered if item.children == t1.addresses)
    assert pair.occurrences == 2


def test_modality_agnostic_address_stream_can_form_composition() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest_address_stream(("audio:A", "audio:B", "audio:X"), provenance="clip-1")
    memory.ingest_address_stream(("audio:A", "audio:B", "audio:Y"), provenance="clip-2")
    engine = AddressCompositionEngine(memory)
    discovered = engine.discover()
    assert any(item.children == ("audio:A", "audio:B") for item in discovered)
