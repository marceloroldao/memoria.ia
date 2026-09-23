from __future__ import annotations

import os

import pytest

from memoria_resolutiva.topological_bdr_persistence import (
    load_snapshot_bdr,
    load_snapshot_from_backend,
    save_snapshot_bdr,
    save_snapshot_to_backend,
)
from memoria_resolutiva.topological_memory import AddressSpace, TemporalEventStore, TemporalOperator
from memoria_resolutiva.topological_persistence import load_snapshot, save_snapshot


class FakeAtomicBackend:
    def __init__(self, state: dict[str, bytes] | None = None) -> None:
        self.state = {} if state is None else state
        self.sequence = 0

    def write_batch(self, puts: list[tuple[str, bytes]]) -> int:
        updated = dict(self.state)
        for key, value in puts:
            updated[key] = bytes(value)
        self.state.clear()
        self.state.update(updated)
        self.sequence += 1
        return self.sequence

    def get(self, key: str) -> bytes | None:
        return self.state.get(key)


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


def _semantic_projection(addresses: AddressSpace, store: TemporalEventStore, raw_addresses: tuple[str, ...]) -> dict:
    current = store.resolve("minha camisa", "cor", TemporalOperator.CURRENT)
    previous = store.resolve("minha camisa", "cor", TemporalOperator.PREVIOUS_STATE)
    history = store.resolve("minha camisa", "cor", TemporalOperator.HISTORY)
    diff = store.resolve("minha camisa", "cor", TemporalOperator.STATE_DIFF)
    return {
        "current": (current.sequence, store.value_text(current.value_address)),
        "previous": (previous.sequence, store.value_text(previous.value_address)),
        "history": tuple((sequence, store.value_text(value_address)) for sequence, value_address in history.history),
        "diff": tuple(
            (
                transition.from_sequence,
                store.value_text(transition.from_value_address),
                transition.to_sequence,
                store.value_text(transition.to_value_address),
            )
            for transition in diff.transitions
        ),
        "raw": tuple(addresses.reconstruct_raw(address) for address in raw_addresses),
        "metrics": addresses.metrics(),
    }


def test_bdr_record_mapping_round_trip_preserves_temporal_semantics():
    addresses, store, raw_addresses = _shirt_history()
    backend_state: dict[str, bytes] = {}
    writer = FakeAtomicBackend(backend_state)

    before = _semantic_projection(addresses, store, raw_addresses)
    stats = save_snapshot_to_backend(writer, addresses, store)

    reader = FakeAtomicBackend(backend_state)
    restored_addresses, restored_store = load_snapshot_from_backend(reader)
    after = _semantic_projection(restored_addresses, restored_store, raw_addresses)

    assert stats.events == 3
    assert stats.transitions == 2
    assert stats.nodes == len(addresses._nodes)
    assert stats.physical_records > stats.events + stats.transitions
    assert before == after


def test_bdr_mapping_and_sqlite_oracle_are_semantically_equivalent(tmp_path):
    addresses, store, raw_addresses = _shirt_history()

    sqlite_path = tmp_path / "oracle.sqlite3"
    save_snapshot(sqlite_path, addresses, store)
    sqlite_addresses, sqlite_store = load_snapshot(sqlite_path)

    backend = FakeAtomicBackend()
    save_snapshot_to_backend(backend, addresses, store)
    bdr_addresses, bdr_store = load_snapshot_from_backend(backend)

    assert _semantic_projection(bdr_addresses, bdr_store, raw_addresses) == _semantic_projection(
        sqlite_addresses,
        sqlite_store,
        raw_addresses,
    )


def test_bdr_mapping_restart_continues_internal_event_sequence():
    addresses, store, _ = _shirt_history()
    state: dict[str, bytes] = {}
    save_snapshot_to_backend(FakeAtomicBackend(state), addresses, store)

    restored_addresses, restored_store = load_snapshot_from_backend(FakeAtomicBackend(state))
    event = restored_store.observe_state("minha camisa", "cor", "vermelha")

    assert event.sequence == 32
    assert event.event_id == "E32"
    assert restored_store.value_text(event.value_address) == "vermelha"


def test_bdr_mapping_fails_closed_when_root_or_referenced_record_is_missing():
    with pytest.raises(ValueError, match="missing BDR record"):
        load_snapshot_from_backend(FakeAtomicBackend())

    addresses, store, _ = _shirt_history()
    backend = FakeAtomicBackend()
    save_snapshot_to_backend(backend, addresses, store)
    node_key = next(key for key in backend.state if "/node/" in key)
    del backend.state[node_key]

    with pytest.raises(ValueError, match="missing BDR record"):
        load_snapshot_from_backend(backend)


def test_real_bdr_shared_abi_matches_sqlite_oracle_when_library_is_available(tmp_path):
    library_path = os.environ.get("BDR_ATOMIC_LIB")
    if not library_path:
        pytest.skip("BDR_ATOMIC_LIB is not configured for this test environment")

    addresses, store, raw_addresses = _shirt_history()
    sqlite_path = tmp_path / "oracle.sqlite3"
    bdr_root = tmp_path / "bdr"

    save_snapshot(sqlite_path, addresses, store)
    sqlite_addresses, sqlite_store = load_snapshot(sqlite_path)

    stats = save_snapshot_bdr(bdr_root, library_path, addresses, store)
    bdr_addresses, bdr_store = load_snapshot_bdr(bdr_root, library_path)

    assert stats.bdr_sequence >= 1
    assert _semantic_projection(bdr_addresses, bdr_store, raw_addresses) == _semantic_projection(
        sqlite_addresses,
        sqlite_store,
        raw_addresses,
    )
