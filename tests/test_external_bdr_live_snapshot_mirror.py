"""Private SQLite-backup -> native BDR shadow migration; no production inputs."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import importlib.util
import json
import os
from pathlib import Path
import sqlite3

import pytest

from memoria_resolutiva.external_episode_contract import (
    ExternalEpisodeRequest, FORMAT, canonical,
)
from memoria_resolutiva.external_episode_incremental import (
    IncrementalEpisodeError, IncrementalExternalEpisodeStore,
)

LIBRARY = os.environ.get("BDR_ATOMIC_LIBRARY", "")
pytestmark = pytest.mark.skipif(
    not LIBRARY or not Path(LIBRARY).is_file(), reason="real pinned BDR C ABI required"
)
script = Path(__file__).resolve().parents[1] / "scripts/mirror_external_episode_live_snapshot.py"
spec = importlib.util.spec_from_file_location("external_bdr_shadow_mirror", script)
assert spec and spec.loader
mirror = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mirror)


def episode(i: int) -> ExternalEpisodeRequest:
    plan = f"plan_{i}"
    identity = {
        "system": "live.infinita", "world_id": "nov-live-autonomous-001",
        "entity_id": "nov", "episode_id": "plan:" + plan,
    }
    unsigned = {
        "schema": FORMAT, "record_key": sha256(canonical(identity)).hexdigest(),
        "source": {
            **identity, "source_schema": "npc_episode_v1", "source_kind": "need_outcome",
            "plan_id": plan, "proposal_id": f"pr_{i}", "plan_revision": 0,
        },
        "observation": {
            "logical_tick": i, "need": "curiosity", "target_entity_id": "ancient_tree",
            "strategy_id": "explore", "context": {
                "period": "day", "weather": "clear", "region_id": "clearing", "danger_level": 0.1,
            },
            "outcome": {
                "satisfaction": 0.3, "observed_risk": 0.1, "elapsed_ticks": 3,
                "preemptions": 0, "replans": 0,
            },
        },
        "authority": "observed-outcome-only", "world_write_authority": False,
    }
    return ExternalEpisodeRequest.model_validate({
        **unsigned, "content_sha256": sha256(canonical(unsigned)).hexdigest(),
    })


def checkpoint_for(row: ExternalEpisodeRequest, path: Path) -> None:
    path.write_text(json.dumps({
        "schema": "live-infinita-nov-local-memory-checkpoint/v1",
        "world_id": row.source.world_id, "ledger_identity": "fixture:1234",
        "cursor": 4096, "prefix_sha256": "f" * 64,
        "last_line_sha256": "e" * 64,
        "last_acked_record_key": row.record_key,
        "last_acked_content_sha256": row.content_sha256,
        "confirmed_episodes": row.observation.logical_tick + 1,
    }))
    path.chmod(0o600)


def populated(tmp_path: Path, n: int = 24):
    root = tmp_path / "sqlite"
    store = IncrementalExternalEpisodeStore(root)
    for i in range(n):
        assert store.observe(episode(i))["ack"]
    store.close()
    return root / "external-episodes.sqlite3"


def test_snapshot_mirror_full_parity_checkpoint_no_source_mutation(tmp_path):
    source = populated(tmp_path, 24)
    ckpt = tmp_path / "nov-checkpoint.json"
    checkpoint_for(episode(23), ckpt)
    source_before = source.read_bytes()
    checkpoint_before = ckpt.read_bytes()
    report = mirror.mirror_live_snapshot(
        source, tmp_path / "shadow", library_path=Path(LIBRARY), checkpoint_path=ckpt,
    )
    assert report["source_count"] == report["bdr_count"] == 24
    assert report["checkpoint_ref_present_at_snapshot"]
    assert report["checkpoint_unchanged_during_mirror"]
    assert report["sqlite_source_inode_unchanged"]
    assert report["source_stream_sha256"] == report["bdr_stream_sha256"]
    assert not report["checkpoint_advanced"] and not report["backend_switched"]
    assert not report["world_mutated"] and not report["production_sqlite_modified_by_mirror"]
    assert source.read_bytes() == source_before
    assert ckpt.read_bytes() == checkpoint_before
    assert (tmp_path / "shadow").stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "shadow/parity-report.json").stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "shadow/sqlite-snapshot.sqlite3").stat().st_mode & 0o777 == 0o600
    assert "plan_23" not in (tmp_path / "shadow/parity-report.json").read_text()
    with pytest.raises(IncrementalEpisodeError, match="must not exist"):
        mirror.mirror_live_snapshot(source, tmp_path / "shadow", library_path=Path(LIBRARY))


def test_concurrent_sqlite_writer_is_never_stopped_or_modified_by_mirror(tmp_path):
    root = tmp_path / "sqlite"
    store = IncrementalExternalEpisodeStore(root)
    for i in range(16):
        store.observe(episode(i))
    source = root / "external-episodes.sqlite3"
    with ThreadPoolExecutor(max_workers=1) as pool:
        writing = pool.submit(lambda: [store.observe(episode(i)) for i in range(16, 80)])
        report = mirror.mirror_live_snapshot(
            source, tmp_path / "while-writer-active", library_path=Path(LIBRARY),
        )
        writing.result(timeout=20)
    assert 16 <= report["source_count"] <= 80
    assert report["source_count"] == report["bdr_count"]
    assert report["source_stream_sha256"] == report["bdr_stream_sha256"]
    assert store.count == 80
    store.close()
    assert (tmp_path / "while-writer-active/sqlite-snapshot.sqlite3").exists()


def test_corrupt_source_digest_is_rejected_without_touching_source(tmp_path):
    source = populated(tmp_path, 3)
    with sqlite3.connect(source) as db:
        db.execute("UPDATE observations SET content_sha256=? WHERE record_key=?",
                   ("0" * 64, episode(1).record_key))
    original = source.read_bytes()
    with pytest.raises(IncrementalEpisodeError, match="invalid SQLite mirror source|snapshot source contract invalid"):
        mirror.mirror_live_snapshot(source, tmp_path / "bad", library_path=Path(LIBRARY))
    assert source.read_bytes() == original
    assert not (tmp_path / "bad/parity-report.json").exists()


def test_checkpoint_missing_from_snapshot_fails_closed(tmp_path):
    source = populated(tmp_path, 3)
    ckpt = tmp_path / "ckpt.json"
    checkpoint_for(episode(9), ckpt)
    before = ckpt.read_bytes()
    with pytest.raises(IncrementalEpisodeError, match="checkpoint identity absent"):
        mirror.mirror_live_snapshot(
            source, tmp_path / "missing-checkpoint", library_path=Path(LIBRARY),
            checkpoint_path=ckpt,
        )
    assert ckpt.read_bytes() == before


def test_checkpoint_advanced_during_snapshot_is_reported_not_mutated(tmp_path, monkeypatch):
    source = populated(tmp_path, 5)
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint_for(episode(2), checkpoint)
    real_snapshot = mirror._snapshot_sqlite

    def advance_after_backup(a, b):
        real_snapshot(a, b)
        checkpoint_for(episode(4), checkpoint)

    monkeypatch.setattr(mirror, "_snapshot_sqlite", advance_after_backup)
    report = mirror.mirror_live_snapshot(
        source, tmp_path / "moving-cursor", library_path=Path(LIBRARY),
        checkpoint_path=checkpoint,
    )
    assert report["source_count"] == 5
    assert not report["checkpoint_unchanged_during_mirror"]
    assert json.loads(checkpoint.read_text())["last_acked_record_key"] == episode(4).record_key


def test_symlink_and_missing_native_and_disk_budget_block_early(tmp_path, monkeypatch):
    source = populated(tmp_path, 2)
    target = tmp_path / "link"
    target.symlink_to(source)
    with pytest.raises(IncrementalEpisodeError, match="invalid"):
        mirror.mirror_live_snapshot(target, tmp_path / "nope", library_path=Path(LIBRARY))
    with pytest.raises(IncrementalEpisodeError, match="native BDR library"):
        mirror.mirror_live_snapshot(source, tmp_path / "nope", library_path=tmp_path / "missing.so")
    monkeypatch.setattr(mirror, "MAX_SOURCE_BYTES", 1)
    with pytest.raises(IncrementalEpisodeError, match="safety budget"):
        mirror.mirror_live_snapshot(source, tmp_path / "nope", library_path=Path(LIBRARY))
    assert not (tmp_path / "nope").exists()
