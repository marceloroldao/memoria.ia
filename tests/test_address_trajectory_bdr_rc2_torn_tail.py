from __future__ import annotations

import os
from pathlib import Path

import pytest

from memoria_resolutiva.address_trajectory_bdr_persistence import (
    load_address_trajectory_snapshot,
    save_address_trajectory_snapshot,
)
from memoria_resolutiva.address_trajectory_v2 import AddressTrajectoryMemory
from memoria_resolutiva.bdr_atomic_bridge_v2 import BDRAtomicV2


LIB_ENV = "MEMORIA_BDR_ATOMIC_V2_LIB"


def _library() -> Path:
    value = os.environ.get(LIB_ENV)
    if not value:
        pytest.skip(f"{LIB_ENV} is not configured")
    path = Path(value)
    if not path.exists():
        pytest.fail(f"configured BDR Atomic ABI v2 library does not exist: {path}")
    return path


def _wal_file(database: Path) -> Path:
    candidates = sorted(database.rglob("*.bdw4"))
    if len(candidates) != 1:
        pytest.fail(f"expected exactly one BDW4 WAL under {database}, found: {candidates}")
    return candidates[0]


def test_rc2_torn_last_snapshot_recovers_previous_memoria_state(tmp_path: Path) -> None:
    library = _library()
    database = tmp_path / "bdr-torn-tail"
    memory = AddressTrajectoryMemory()
    memory.ingest("Meu veículo é azul.")

    with BDRAtomicV2(library, database, durability=BDRAtomicV2.BATCH_SYNC) as bdr:
        first = save_address_trajectory_snapshot(bdr, memory)
        assert bdr.durable_sequence() == first.bdr_sequence

    wal = _wal_file(database)
    first_boundary = wal.stat().st_size
    first_snapshot = memory.snapshot()

    memory.ingest("Meu veículo ficou preto.")
    with BDRAtomicV2(library, database, durability=BDRAtomicV2.BATCH_SYNC) as bdr:
        second = save_address_trajectory_snapshot(bdr, memory)
        assert second.bdr_sequence > first.bdr_sequence
        assert bdr.durable_sequence() == second.bdr_sequence

    complete_size = wal.stat().st_size
    assert complete_size > first_boundary

    # Simulate a process/power failure while the last logical Memoria mutation is
    # being appended: preserve the previous committed snapshot and only a prefix
    # of the next BDW4 frame.
    torn_size = first_boundary + max(1, (complete_size - first_boundary) // 2)
    with wal.open("r+b") as handle:
        handle.truncate(torn_size)
    assert first_boundary < wal.stat().st_size < complete_size

    with BDRAtomicV2(library, database, durability=BDRAtomicV2.BATCH_SYNC) as reopened:
        restored = load_address_trajectory_snapshot(reopened)
        assert restored.snapshot() == first_snapshot
        assert reopened.last_sequence() == first.bdr_sequence
        assert reopened.durable_sequence() == first.bdr_sequence

    # Recovery must repair the torn suffix to the last valid atomic boundary.
    assert wal.stat().st_size == first_boundary

    # A second cold reopen must be deterministic and must not repair anything new.
    with BDRAtomicV2(library, database, durability=BDRAtomicV2.BATCH_SYNC) as reopened_again:
        restored_again = load_address_trajectory_snapshot(reopened_again)
        assert restored_again.snapshot() == first_snapshot
        assert reopened_again.last_sequence() == first.bdr_sequence
