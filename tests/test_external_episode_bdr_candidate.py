"""Native BDR candidate parity: skips if the exact C ABI was not built.

Set BDR_ATOMIC_LIBRARY to pinned resolutive-DB v1.2.0-rc4's shared library
and put that tag's bdr Python package on PYTHONPATH for the native CI gate.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3

import pytest

from memoria_resolutiva.external_episode_contract import (
    ExternalEpisodeRequest, FORMAT, canonical,
)
from memoria_resolutiva.external_episode_bdr_candidate import (
    BdrExternalEpisodeCandidate, COUNT, MARKER, _id_key, _seq_key,
)
from memoria_resolutiva.external_episode_incremental import (
    IncrementalEpisodeError, IncrementalExternalEpisodeStore,
)

LIBRARY = os.getenv("BDR_ATOMIC_LIBRARY", "")
pytestmark = pytest.mark.skipif(
    not LIBRARY or not Path(LIBRARY).is_file(), reason="exact native BDR library required",
)


def request(i: int, *, world: str = "nov-live-autonomous-001") -> ExternalEpisodeRequest:
    plan = f"plan_{i}"
    identity = {
        "system": "live.infinita", "world_id": world,
        "entity_id": "nov", "episode_id": "plan:" + plan,
    }
    unsigned = {
        "schema": FORMAT, "record_key": sha256(canonical(identity)).hexdigest(),
        "source": {
            **identity, "source_schema": "npc_episode_v1", "source_kind": "need_outcome",
            "plan_id": plan, "proposal_id": "pr_" + plan, "plan_revision": 0,
        },
        "observation": {
            "logical_tick": i, "need": "curiosity",
            "target_entity_id": "ancient_tree", "strategy_id": "explore",
            "context": {
                "period": "night", "weather": "clear",
                "region_id": "clearing", "danger_level": 0.35,
            },
            "outcome": {
                "satisfaction": 0.3, "observed_risk": 0.35, "elapsed_ticks": 3,
                "preemptions": 0, "replans": 0,
            },
        },
        "authority": "observed-outcome-only", "world_write_authority": False,
    }
    return ExternalEpisodeRequest.model_validate({
        **unsigned, "content_sha256": sha256(canonical(unsigned)).hexdigest(),
    })


def edges(core):
    return tuple(
        (
            e.subject, e.predicate, e.object, e.evidence_id, e.source_text,
            e.namespace, e.epoch, e.provenance, e.origin, e.confidence,
        )
        for e in core.evidence_history(namespace="live:nov-live-autonomous-001")
    )


def open_bdr(path: Path):
    return BdrExternalEpisodeCandidate(path, library_path=LIBRARY)


def test_explicit_native_library_or_fail_closed(tmp_path):
    with pytest.raises(IncrementalEpisodeError, match="pinned native BDR library"):
        BdrExternalEpisodeCandidate(tmp_path / "missing", library_path="/does-not-exist/libbdr.so")


def test_real_sqlite_bdr_parity_reopen_duplicate_and_conflict(tmp_path):
    sqlite = IncrementalExternalEpisodeStore(tmp_path / "sqlite")
    bdr = open_bdr(tmp_path / "bdr")
    for i in range(100):
        row = request(i)
        first = sqlite.observe(row)
        second = bdr.observe(row)
        assert first["ack"] and second["ack"] and first["stored"] == second["stored"]
        assert first["record_key"] == second["record_key"]
        assert first["content_sha256"] == second["content_sha256"]
        assert second["persistence"]["backend"] == "bdr-incremental-candidate"
        assert second["persistence"]["durable_sequence"] > 0
        assert sqlite.observe(row)["stored"] is False
        assert bdr.observe(row)["stored"] is False
    assert sqlite.count == bdr.count == 100
    assert edges(sqlite.core) == edges(bdr.core)
    before = bdr._db.last_sequence()
    row = request(0)
    changed = row.model_dump(mode="json")
    changed["observation"]["outcome"]["satisfaction"] = 0.95
    changed["content_sha256"] = sha256(canonical({
        k: v for k, v in changed.items() if k != "content_sha256"
    })).hexdigest()
    with pytest.raises(IncrementalEpisodeError, match="different observed content"):
        bdr.observe(ExternalEpisodeRequest.model_validate(changed))
    assert bdr._db.last_sequence() == before
    bdr.close()
    sqlite.close()
    reopened_sqlite = IncrementalExternalEpisodeStore(tmp_path / "sqlite")
    reopened_bdr = open_bdr(tmp_path / "bdr")
    assert reopened_bdr.count == reopened_sqlite.count == 100
    assert edges(reopened_bdr.core) == edges(reopened_sqlite.core)
    assert reopened_bdr.observe(request(0))["stored"] is False
    reopened_bdr.close()
    reopened_sqlite.close()


def test_native_single_batch_exact_durability_and_index(tmp_path):
    from bdr.atomic import AtomicBDR
    root = tmp_path / "atomic"
    store = open_bdr(root)
    previous = store._db.last_sequence()
    rec = store.observe(request(1))
    assert store._db.last_sequence() == previous + 1
    assert store._db.durable_sequence() == store._db.last_sequence()
    assert store._db.get(COUNT) == b"1"
    assert store._db.get(MARKER) is not None
    assert store._db.get(_seq_key(0)) == rec["record_key"].encode("ascii")
    assert store._db.get(_id_key(rec["record_key"])) is not None
    store.close()
    native = AtomicBDR.open(root, library_path=LIBRARY)
    assert native.get(COUNT) == b"1"
    assert native.get(_seq_key(0)) == rec["record_key"].encode("ascii")
    native.close()


def test_recovery_detects_index_corruption_without_ack(tmp_path):
    from bdr.atomic import AtomicBDR
    root = tmp_path / "corrupt"
    store = open_bdr(root)
    store.observe(request(0))
    store.close()
    native = AtomicBDR.open(root, library_path=LIBRARY)
    native.put_many({_seq_key(0): b"0" * 64})
    native.close()
    with pytest.raises(IncrementalEpisodeError, match="index|missing"):
        open_bdr(root)


def test_sqlite_mirror_is_copy_only_and_idempotent(tmp_path):
    sqlite = IncrementalExternalEpisodeStore(tmp_path / "sqlite")
    for i in range(25):
        sqlite.observe(request(i))
    sqlite.close()
    before = (tmp_path / "sqlite/external-episodes.sqlite3").stat()
    bdr = open_bdr(tmp_path / "bdr")
    original = tmp_path / "sqlite/external-episodes.sqlite3"
    assert bdr.mirror_sqlite_snapshot(original) == 25
    assert bdr.mirror_sqlite_snapshot(original) == 0
    bdr.close()
    reopened = open_bdr(tmp_path / "bdr")
    assert reopened.count == 25
    sqlite_restored = IncrementalExternalEpisodeStore(tmp_path / "sqlite")
    assert edges(reopened.core) == edges(sqlite_restored.core)
    assert original.stat().st_size == before.st_size
    assert original.stat().st_mtime_ns == before.st_mtime_ns
    reopened.close()
    sqlite_restored.close()


def test_native_torn_bdw4_tail_discards_whole_episode_batch(tmp_path):
    """A torn final transaction must not expose data without index/count."""
    root = tmp_path / "torn-bdw4"
    wal = root / "atomic.bdw4"
    base = open_bdr(root)
    base.observe(request(1))
    base.close()
    first_size = wal.stat().st_size
    second = open_bdr(root)
    second.observe(request(2))
    second.close()
    full_size = wal.stat().st_size
    assert full_size > first_size
    with wal.open("r+b") as fp:
        fp.truncate(first_size + max(1, (full_size - first_size) // 2))
    recovered = open_bdr(root)
    assert recovered.count == 1
    assert recovered.observe(request(1))["stored"] is False
    assert recovered.observe(request(2))["stored"] is True
    assert recovered._db.durable_sequence() == recovered._db.last_sequence()
    recovered.close()


def test_checkpoint_is_explicitly_not_migrated(tmp_path):
    sqlite = IncrementalExternalEpisodeStore(tmp_path / "sqlite")
    sqlite.observe(request(0))
    sqlite.close()
    bdr = open_bdr(tmp_path / "bdr")
    assert bdr.mirror_sqlite_snapshot(tmp_path / "sqlite/external-episodes.sqlite3") == 1
    assert bdr._db.get("nov-ingest.checkpoint.json") is None
    bdr.close()
