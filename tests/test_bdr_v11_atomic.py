from __future__ import annotations

import pytest

from memoria_resolutiva.bdr_store import BDRResolutiveMemory, native_bdr_available

pytestmark = pytest.mark.skipif(
    not native_bdr_available(), reason="native BDR extension not built"
)


def test_one_logical_memory_advances_one_atomic_sequence(tmp_path):
    db = BDRResolutiveMemory(tmp_path / "atomic-sequence", max_layer=3)
    try:
        before = db.db.last_sequence
        db.add("m1", bytes(range(128)))
        after_first = db.db.last_sequence
        db.add("m2", (b"atomic-memory-" * 31)[:333])
        after_second = db.db.last_sequence

        assert after_first == before + 1
        assert after_second == after_first + 1
        assert db.db.durable_sequence == after_second
    finally:
        db.close()


def test_torn_final_bdw4_discards_entire_logical_memory(tmp_path):
    root = tmp_path / "atomic-torn-tail"
    wal = root / "atomic.bdw4"

    first = BDRResolutiveMemory(root, max_layer=3)
    first.add("base", bytes(range(96)))
    first.close()
    first_size = wal.stat().st_size

    second = BDRResolutiveMemory(root, max_layer=3)
    second.add("victim", (b"second-logical-memory-" * 17)[:287])
    second.close()
    complete_size = wal.stat().st_size

    assert complete_size > first_size

    # Simulate a process/storage failure that leaves only a prefix of the final
    # BDW4 frame. Recovery must keep the prior committed logical memory and
    # reject every physical record belonging to the torn logical memory.
    torn_size = first_size + max(1, (complete_size - first_size) // 2)
    with wal.open("r+b") as fh:
        fh.truncate(torn_size)

    reopened = BDRResolutiveMemory(root, max_layer=3)
    try:
        assert reopened.reconstruct("base") == bytes(range(96))
        with pytest.raises(KeyError):
            reopened.reconstruct("victim")

        stats = reopened.stats()
        assert stats["memories"] == 1
    finally:
        reopened.close()


def test_reopen_preserves_atomic_metadata_and_payload(tmp_path):
    root = tmp_path / "atomic-reopen"
    expected = {
        f"m{i}": bytes((j * (i + 3)) % 251 for j in range(64 + i * 13))
        for i in range(8)
    }

    db = BDRResolutiveMemory(root, max_layer=3)
    for memory_id, payload in expected.items():
        db.add(memory_id, payload)
    before = db.stats()
    seq = db.db.durable_sequence
    db.close()

    reopened = BDRResolutiveMemory(root, max_layer=3)
    try:
        assert reopened.stats() == before
        assert reopened.db.durable_sequence == seq
        for memory_id, payload in expected.items():
            assert reopened.reconstruct(memory_id) == payload
    finally:
        reopened.close()
