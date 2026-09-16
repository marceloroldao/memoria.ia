from __future__ import annotations

from memoria_resolutiva.topological_memory import AddressSpace, TemporalEventStore, TemporalOperator
from memoria_resolutiva.topological_persistence import load_snapshot, save_snapshot


def _shirt_history() -> tuple[AddressSpace, TemporalEventStore, tuple[str, str, str]]:
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    raw_addresses: list[str] = []
    for sequence, color in ((12, "azul"), (24, "preta"), (31, "branca")):
        ingestion = addresses.ingest_text(f"Minha camisa é {color}.")
        raw_addresses.append(ingestion.raw_memory_address)
        store.observe_state(
            "minha camisa",
            "cor",
            color,
            sequence=sequence,
            raw_memory_address=ingestion.raw_memory_address,
        )
    return addresses, store, tuple(raw_addresses)


def test_sqlite_restart_preserves_addresses_history_transitions_and_raw(tmp_path):
    addresses, store, raw_addresses = _shirt_history()
    path = tmp_path / "topology.sqlite3"

    before_current = store.resolve("minha camisa", "cor", TemporalOperator.CURRENT)
    before_history = store.resolve("minha camisa", "cor", TemporalOperator.HISTORY)
    before_diff = store.resolve("minha camisa", "cor", TemporalOperator.STATE_DIFF)
    before_metrics = addresses.metrics()

    stats = save_snapshot(path, addresses, store)
    restored_addresses, restored_store = load_snapshot(path)

    after_current = restored_store.resolve("minha camisa", "cor", TemporalOperator.CURRENT)
    after_history = restored_store.resolve("minha camisa", "cor", TemporalOperator.HISTORY)
    after_diff = restored_store.resolve("minha camisa", "cor", TemporalOperator.STATE_DIFF)

    assert stats.events == 3
    assert stats.transitions == 2
    assert after_current == before_current
    assert after_history == before_history
    assert after_diff == before_diff
    assert restored_addresses.metrics() == before_metrics

    for raw_address in raw_addresses:
        assert restored_addresses.reconstruct_raw(raw_address) == addresses.reconstruct_raw(raw_address)

    for value in ("azul", "preta", "branca"):
        assert restored_addresses.resolve("value", value).address == addresses.resolve("value", value).address


def test_restart_continues_monotonic_sequence_without_reusing_event_ids(tmp_path):
    addresses, store, _raw_addresses = _shirt_history()
    path = tmp_path / "topology.sqlite3"
    save_snapshot(path, addresses, store)

    restored_addresses, restored_store = load_snapshot(path)
    event = restored_store.observe_state("minha camisa", "cor", "vermelha")

    assert event.sequence == 32
    assert event.event_id == "E32"
    assert restored_store.value_text(event.value_address) == "vermelha"
    assert len(restored_store.transitions_for(event.subject_address, event.attribute_address)) == 3


def test_snapshot_is_domain_independent_across_entity_types(tmp_path):
    addresses = AddressSpace()
    store = TemporalEventStore(addresses)
    observations = [
        ("meu carro", "cor", "azul"),
        ("sensor sala", "temperatura", "23"),
        ("servidor principal", "ip", "10.0.0.2"),
        ("robo 1", "position", "x2y7"),
        ("meu gato", "nome", "Alt"),
    ]
    for subject, attribute, value in observations:
        store.observe_state(subject, attribute, value)

    path = tmp_path / "mixed.sqlite3"
    save_snapshot(path, addresses, store)
    restored_addresses, restored_store = load_snapshot(path)

    for subject, attribute, value in observations:
        result = restored_store.resolve(subject, attribute, TemporalOperator.CURRENT)
        assert restored_store.value_text(result.value_address) == value.casefold()
        assert restored_addresses.resolve("entity", subject) is not None


def test_empty_snapshot_fails_closed(tmp_path):
    path = tmp_path / "empty.sqlite3"
    try:
        load_snapshot(path)
    except ValueError as error:
        assert "empty" in str(error)
    else:
        raise AssertionError("empty snapshot must fail closed")
