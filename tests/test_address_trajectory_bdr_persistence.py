from __future__ import annotations

from memoria_resolutiva.address_trajectory_bdr_persistence import (
    load_address_trajectory_snapshot,
    save_address_trajectory_snapshot,
)
from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory


class FakeAtomicBackend:
    def __init__(self) -> None:
        self.records: dict[bytes, bytes] = {}
        self.sequence = 0
        self.batch_sizes: list[int] = []

    def write_batch(self, puts: list[tuple[bytes, bytes]]) -> int:
        pending = dict(self.records)
        for key, value in puts:
            pending[bytes(key)] = bytes(value)
        self.records = pending
        self.sequence += 1
        self.batch_sizes.append(len(puts))
        return self.sequence

    def get(self, key: bytes) -> bytes | None:
        return self.records.get(bytes(key))


def _resolve_signature(memory: AddressTrajectoryMemory, query: str) -> list[tuple[object, ...]]:
    return [
        (
            match.trajectory_id,
            match.raw_text,
            match.overlap,
            match.ordered_overlap,
            match.adjacency_overlap,
            match.query_coverage_num,
            match.query_coverage_den,
            match.terminal_surface,
            match.structural_key,
        )
        for match in memory.resolve(query, limit=10)
    ]


def test_v2_snapshot_round_trip_preserves_addresses_raw_text_and_resolve() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("Meu veículo é azul.")
    memory.ingest("Meu veículo ficou preto.")
    memory.ingest("Meu veículo agora é branco.")
    memory.ingest("ação ação repetida")
    memory.ingest("UTF-8: coração, ação, café, 日本語")

    before_snapshot = memory.snapshot()
    before_resolve = _resolve_signature(memory, "veículo branco")

    backend = FakeAtomicBackend()
    stats = save_address_trajectory_snapshot(backend, memory)
    restored = load_address_trajectory_snapshot(backend)

    assert stats.trajectories == len(before_snapshot)
    assert stats.physical_records == len(before_snapshot) + 1
    assert backend.batch_sizes == [len(before_snapshot) + 1]
    assert restored.snapshot() == before_snapshot
    assert _resolve_signature(restored, "veículo branco") == before_resolve


def test_v2_restore_continues_trajectory_ids_without_drift() -> None:
    memory = AddressTrajectoryMemory()
    first = memory.ingest("gato Alt")
    second = memory.ingest("gato Alt novamente")

    backend = FakeAtomicBackend()
    save_address_trajectory_snapshot(backend, memory)
    restored = load_address_trajectory_snapshot(backend)
    third = restored.ingest("gato Alt depois do restart")

    assert first.trajectory_id == "AT1"
    assert second.trajectory_id == "AT2"
    assert third.trajectory_id == "AT3"


def test_missing_physical_record_fails_closed_instead_of_partial_restore() -> None:
    memory = AddressTrajectoryMemory()
    memory.ingest("primeira trajetória")
    memory.ingest("segunda trajetória")

    backend = FakeAtomicBackend()
    save_address_trajectory_snapshot(backend, memory)
    trajectory_keys = sorted(key for key in backend.records if b"/trajectory/" in key)
    del backend.records[trajectory_keys[0]]

    try:
        load_address_trajectory_snapshot(backend)
    except ValueError as exc:
        assert "missing BDR record" in str(exc)
    else:
        raise AssertionError("partial V2 snapshot must fail closed")
