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
import memoria_resolutiva.external_episode_bdr_mirror as mirror_module

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


def _checkpoint(path: Path, row: ExternalEpisodeRequest) -> None:
    path.write_text(json.dumps({
        "schema": "live-infinita-nov-local-memory-checkpoint/v1",
        "world_id": row.source.world_id,
        "ledger_identity": "fixture:inode",
        "cursor": 4096,
        "prefix_sha256": "f" * 64,
        "last_line_sha256": "e" * 64,
        "last_acked_record_key": row.record_key,
        "last_acked_content_sha256": row.content_sha256,
    }))
    path.chmod(0o600)


def test_read_only_checkpoint_watermark_in_original_mirror(tmp_path):
    store, source = create_source(tmp_path, 12)
    checkpoint = tmp_path / "nov-ingest.checkpoint.json"
    _checkpoint(checkpoint, episode(11))
    before = checkpoint.read_bytes()
    result = create_verified_mirror(
        source, tmp_path / "with-watermark",
        library_path=LIBRARY, checkpoint_path=checkpoint,
    )
    assert result["source_snapshot_records"] == 12
    assert result["checkpoint_watermark_present"] is True
    assert result["checkpoint_unchanged_during_copy"] is True
    assert result["checkpoint_cursor_at_start"] == 4096
    assert result["sqlite_source_inode_unchanged"] is True
    assert checkpoint.read_bytes() == before
    assert store.observe(episode(12))["stored"]
    store.close()


def test_checkpoint_missing_from_source_blocks_without_success_report(tmp_path):
    store, source = create_source(tmp_path, 4)
    checkpoint = tmp_path / "nov-ingest.checkpoint.json"
    _checkpoint(checkpoint, episode(99))
    original = checkpoint.read_bytes()
    with pytest.raises(BdrMirrorVerificationError, match="checkpoint_identity_missing"):
        create_verified_mirror(
            source, tmp_path / "bad-watermark",
            library_path=LIBRARY, checkpoint_path=checkpoint,
        )
    assert checkpoint.read_bytes() == original
    assert not (tmp_path / "bad-watermark/report.json").exists()
    store.close()


def test_moving_checkpoint_is_reported_not_advanced(tmp_path, monkeypatch):
    store, source = create_source(tmp_path, 5)
    checkpoint = tmp_path / "nov-ingest.checkpoint.json"
    _checkpoint(checkpoint, episode(2))
    real_copy = mirror_module._snapshot_live_sqlite

    def change_checkpoint_after_copy(src: Path, dest: Path) -> None:
        real_copy(src, dest)
        _checkpoint(checkpoint, episode(4))

    monkeypatch.setattr(mirror_module, "_snapshot_live_sqlite", change_checkpoint_after_copy)
    report = create_verified_mirror(
        source, tmp_path / "moving", library_path=LIBRARY,
        checkpoint_path=checkpoint,
    )
    assert report["source_snapshot_records"] == 5
    assert report["checkpoint_watermark_present"] is True
    assert report["checkpoint_unchanged_during_copy"] is False
    assert report["production_checkpoint_advanced"] is False
    assert json.loads(checkpoint.read_text())["last_acked_record_key"] == episode(4).record_key
    store.close()


def test_source_size_symlink_and_checkpoint_corruption_fail_early(tmp_path, monkeypatch):
    store, source = create_source(tmp_path, 2)
    link = tmp_path / "source-link"
    link.symlink_to(source)
    with pytest.raises(BdrMirrorVerificationError, match="source_symlink"):
        create_verified_mirror(link, tmp_path / "out1", library_path=LIBRARY)
    monkeypatch.setattr(mirror_module, "MAX_SOURCE_BYTES", 1)
    with pytest.raises(BdrMirrorVerificationError, match="source_exceeds_space_budget"):
        create_verified_mirror(source, tmp_path / "out2", library_path=LIBRARY)
    monkeypatch.undo()
    ckpt = tmp_path / "bad-checkpoint"
    ckpt.write_text("{}")
    with pytest.raises(BdrMirrorVerificationError, match="checkpoint_schema_mismatch"):
        create_verified_mirror(
            source, tmp_path / "out3", library_path=LIBRARY, checkpoint_path=ckpt,
        )
    assert not (tmp_path / "out2").exists()
    assert not (tmp_path / "out3").exists()
    store.close()
