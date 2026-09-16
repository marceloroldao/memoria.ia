from __future__ import annotations

import os
from pathlib import Path

import pytest

from memoria_resolutiva.address_trajectory_bdr_persistence import load_address_trajectory_snapshot, save_address_trajectory_snapshot
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


def _fixture() -> AddressTrajectoryMemory:
    memory = AddressTrajectoryMemory()
    memory.ingest("Meu veículo é azul.")
    memory.ingest("Meu veículo ficou preto.")
    memory.ingest("Meu veículo agora é branco.")
    memory.ingest("UTF-8: coração, ação, café, 日本語")
    return memory


def test_real_rc1_round_trip_survives_cold_reopen(tmp_path: Path) -> None:
    library = _library()
    database = tmp_path / "bdr"
    memory = _fixture()
    before = memory.snapshot()
    before_resolve = memory.resolve("veículo branco", limit=10)

    with BDRAtomicV2(library, database, durability=BDRAtomicV2.BATCH_SYNC) as bdr:
        stats = save_address_trajectory_snapshot(bdr, memory)
        assert stats.bdr_sequence == bdr.last_sequence()
        assert bdr.durable_sequence() == bdr.last_sequence()

    # New native handle: this is a real cold reopen from BDR files/WAL.
    with BDRAtomicV2(library, database, durability=BDRAtomicV2.BATCH_SYNC) as reopened:
        restored = load_address_trajectory_snapshot(reopened)
        assert restored.snapshot() == before
        assert restored.resolve("veículo branco", limit=10) == before_resolve
        assert reopened.last_sequence() >= 1
        assert reopened.durable_sequence() == reopened.last_sequence()

    next_trajectory = restored.ingest("Meu veículo permanece branco.")
    assert next_trajectory.trajectory_id == "AT5"


@pytest.mark.parametrize(
    ("durability", "must_be_durable_on_return"),
    [
        (BDRAtomicV2.ASYNC, False),
        (BDRAtomicV2.BATCH_SYNC, True),
        (BDRAtomicV2.PER_OPERATION_SYNC, True),
    ],
    ids=["async", "batch-sync", "per-operation-sync"],
)
def test_real_rc1_durability_contract_and_cold_restart(
    tmp_path: Path, durability: int, must_be_durable_on_return: bool
) -> None:
    library = _library()
    database = tmp_path / f"bdr-{durability}"
    memory = _fixture()
    before = memory.snapshot()

    with BDRAtomicV2(library, database, durability=durability) as bdr:
        stats = save_address_trajectory_snapshot(bdr, memory)
        last_after_write = bdr.last_sequence()
        durable_after_write = bdr.durable_sequence()
        assert stats.bdr_sequence == last_after_write
        assert 0 <= durable_after_write <= last_after_write
        if must_be_durable_on_return:
            assert durable_after_write == last_after_write
        else:
            # Async is allowed to lag; do not falsely require or forbid eager durability.
            bdr.sync()
            assert bdr.durable_sequence() == bdr.last_sequence()

    with BDRAtomicV2(library, database, durability=durability) as reopened:
        restored = load_address_trajectory_snapshot(reopened)
        assert restored.snapshot() == before
        assert reopened.last_sequence() >= 1
        assert reopened.durable_sequence() == reopened.last_sequence()


def test_real_rc1_multiple_batches_preserve_sequence_and_latest_snapshot(tmp_path: Path) -> None:
    library = _library()
    database = tmp_path / "bdr-multiple-batches"
    memory = AddressTrajectoryMemory()
    sequences: list[int] = []

    with BDRAtomicV2(library, database, durability=BDRAtomicV2.BATCH_SYNC) as bdr:
        for observation in (
            "Meu veículo é azul.",
            "Meu veículo ficou preto.",
            "Meu veículo agora é branco.",
        ):
            memory.ingest(observation)
            stats = save_address_trajectory_snapshot(bdr, memory)
            sequences.append(stats.bdr_sequence)
            assert bdr.durable_sequence() == bdr.last_sequence()

    assert sequences == sorted(sequences)
    assert len(set(sequences)) == len(sequences)
    before = memory.snapshot()

    with BDRAtomicV2(library, database, durability=BDRAtomicV2.BATCH_SYNC) as reopened:
        restored = load_address_trajectory_snapshot(reopened)
        assert restored.snapshot() == before
        assert reopened.last_sequence() == sequences[-1]
        assert reopened.durable_sequence() == sequences[-1]
