"""True native side-by-side mirroring; no production fixtures or credentials."""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import sqlite3
from threading import Thread

import pytest

from memoria_resolutiva.external_episode_contract import (
    ExternalEpisodeRequest, FORMAT, canonical,
)
from memoria_resolutiva.external_episode_incremental import IncrementalExternalEpisodeStore
from memoria_resolutiva.external_episode_bdr_mirror import (
    BdrMirrorVerificationError, _snapshot_live_sqlite, create_verified_mirror,
)

LIBRARY = os.getenv("BDR_ATOMIC_LIBRARY", "")
pytestmark = pytest.mark.skipif(
    not LIBRARY or not Path(LIBRARY).is_file(),
    reason="pinned native BDR C ABI bridge required",
)


def episode(i: int, *, world: str = "nov-live-autonomous-001") -> ExternalEpisodeRequest:
    plan = f"plan_{i}"
    identity = {
        "system": "live.infinita", "world_id": world,
        "entity_id": "nov", "episode_id": "plan:" + plan,
    }
    unsigned = {
        "schema": FORMAT, "record_key": sha256(canonical(identity)).hexdigest(),
        "source": {
            **identity, "source_schema": "npc_episode_v1", "source_kind": "need_outcome",
            "plan_id": plan, "proposal_id": "proposal_" + plan, "plan_revision": 0,
        },
        "observation": {
            "logical_tick": i, "need": "curiosity",
            "target_entity_id": "ancient_tree", "strategy_id": "explore",
            "context": {
                "period": "night", "weather": "clear", "region_id": "clearing", "danger_level": .35,
            },
            "outcome": {
                "satisfaction": .3, "observed_risk": .35, "elapsed_ticks": 3,
                "preemptions": 0, "replans": 0,
            },
        },
        "authority": "observed-outcome-only", "world_write_authority": False,
    }
    return ExternalEpisodeRequest.model_validate({
        **unsigned, "content_sha256": sha256(canonical(unsigned)).hexdigest(),
    })


def create_source(root: Path, count: int) -> tuple[IncrementalExternalEpisodeStore, Path]:
    source = root / "source"
    store = IncrementalExternalEpisodeStore(source)
    for index in range(count):
        assert store.observe(episode(index))["ack"]
    return store, store.path


def test_online_snapshot_keeps_wal_and_source_untouched(tmp_path):
    store, source = create_source(tmp_path, 25)
    # Keep SQLite source writer open, including its WAL.
    before = source.stat()
    before_wal = source.with_name(source.name + "-wal")
    assert before_wal.is_file()
    _snapshot_live_sqlite(source, tmp_path / "online-snapshot.sqlite3")
    snap = sqlite3.connect(tmp_path / "online-snapshot.sqlite3")
    try:
        assert snap.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert snap.execute("SELECT COUNT(*) FROM observations").fetchone() == (25,)
    finally:
        snap.close()
    assert source.stat().st_size == before.st_size
    assert source.stat().st_mtime_ns == before.st_mtime_ns
    assert store.count == 25
    assert store.observe(episode(25))["stored"] is True
    store.close()


def test_verified_real_mirror_live_writer_and_cold_replay(tmp_path):
    store, source = create_source(tmp_path, 100)
    output = tmp_path / "mirror-run"
    before = source.stat()
    result = create_verified_mirror(source, output, library_path=LIBRARY)
    assert result["schema"] == "memoria-v2-bdr-observed-episode-mirror-proof/v1"
    assert result["source_snapshot_records"] == result["inserted_into_bdr"] == 100
    assert result["verified_cold_restart"] and result["verified_idempotent_replay"]
    assert result["bdr_durable_sequence"] == 100
    assert result["backend_cutover"] is False
    assert result["production_checkpoint_advanced"] is False
    assert result["world_mutated"] is False
    assert output.stat().st_mode & 0o777 == 0o700
    assert (output / "report.json").stat().st_mode & 0o777 == 0o600
    assert source.stat().st_size == before.st_size
    assert source.stat().st_mtime_ns == before.st_mtime_ns
    assert store.observe(episode(100))["stored"] is True  # online source still writable
    with pytest.raises(BdrMirrorVerificationError, match="output_already_exists"):
        create_verified_mirror(source, output, library_path=LIBRARY)
    store.close()
    assert json.loads((output / "report.json").read_text()) == result


def test_reject_bad_snapshot_and_never_claim_success(tmp_path):
    store, source = create_source(tmp_path, 2)
    store.close()
    with sqlite3.connect(source) as db:
        db.execute("UPDATE observations SET content_sha256=? WHERE rowid=1", ("0"*64,))
    with pytest.raises(Exception):
        create_verified_mirror(source, tmp_path / "bad-mirror", library_path=LIBRARY)
    assert not (tmp_path / "bad-mirror/report.json").exists()


def test_different_source_records_are_not_hidden_by_same_count(tmp_path):
    store, source = create_source(tmp_path, 3)
    first = create_verified_mirror(source, tmp_path / "first", library_path=LIBRARY)
    # A second consistent source snapshot can grow without changing first.
    assert store.observe(episode(3))["stored"]
    second = create_verified_mirror(source, tmp_path / "second", library_path=LIBRARY)
    assert first["source_snapshot_records"] == 3
    assert second["source_snapshot_records"] == 4
    assert first["record_manifest_sha256"] != second["record_manifest_sha256"]
    assert first["evidence_graph_sha256"] != second["evidence_graph_sha256"]
    store.close()


def test_refuse_record_count_limit_without_receipt(tmp_path):
    store, source = create_source(tmp_path, 4)
    with pytest.raises(BdrMirrorVerificationError, match="snapshot_exceeds_record_limit"):
        create_verified_mirror(source, tmp_path / "bounded", library_path=LIBRARY, max_records=3)
    assert not (tmp_path / "bounded/report.json").exists()
    store.close()
