"""Verified, copy-only mirror of a live V2 SQLite journal into BDR.

The source SQLite journal is opened *read-only*, copied with SQLite's online
backup API into a private destination, and never held open during the native
BDR replay. The resulting candidate is not a backend switch or Nov checkpoint.
"""
from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
from time import monotonic
from typing import Any

from .external_episode_bdr_candidate import (
    BdrExternalEpisodeCandidate, _id_key, _seq_key,
)
from .external_episode_incremental import (
    IncrementalEpisodeError, IncrementalExternalEpisodeStore,
)

SOURCE_NAME = "external-episodes.sqlite3"
REPORT_SCHEMA = "memoria-v2-bdr-observed-episode-mirror-proof/v1"
MAX_RECORDS = 100_000
MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_CHECKPOINT_BYTES = 8192
CHECKPOINT_SCHEMA = "live-infinita-nov-local-memory-checkpoint/v1"
EDGE_FIELDS = (
    "subject", "predicate", "object", "evidence_id", "source_text",
    "namespace", "epoch", "provenance", "origin", "confidence",
)


class BdrMirrorVerificationError(IncrementalEpisodeError):
    pass


def _edge_digest(core: Any) -> str:
    entries = [
        [getattr(edge, field) for field in EDGE_FIELDS]
        for edge in core._edges
    ]
    return sha256(json.dumps(
        entries, ensure_ascii=False, sort_keys=False,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _file_size(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def _read_checkpoint(path: Path | None) -> tuple[bytes | None, dict[str, Any] | None]:
    """Capture a watermark without advancing it or logging identities."""
    if path is None:
        return None, None
    if path.is_symlink():
        raise BdrMirrorVerificationError("checkpoint_symlink")
    with path.open("rb") as stream:
        raw = stream.read(MAX_CHECKPOINT_BYTES + 1)
    if len(raw) > MAX_CHECKPOINT_BYTES:
        raise BdrMirrorVerificationError("checkpoint_oversized")
    try:
        entry = json.loads(raw)
    except ValueError as exc:
        raise BdrMirrorVerificationError("checkpoint_invalid_json") from exc
    if not isinstance(entry, dict) or entry.get("schema") != CHECKPOINT_SCHEMA:
        raise BdrMirrorVerificationError("checkpoint_schema_mismatch")
    cursor = entry.get("cursor")
    if isinstance(cursor, bool) or not isinstance(cursor, int) or cursor < 0:
        raise BdrMirrorVerificationError("checkpoint_cursor_invalid")
    key, digest = entry.get("last_acked_record_key"), entry.get("last_acked_content_sha256")
    if cursor:
        if not all(isinstance(v, str) and len(v) == 64 and
                   all(ch in "0123456789abcdef" for ch in v) for v in (key, digest)):
            raise BdrMirrorVerificationError("checkpoint_identity_invalid")
    elif key is not None or digest is not None:
        raise BdrMirrorVerificationError("checkpoint_empty_cursor_invalid")
    return raw, entry


def _checkpoint_in_snapshot(snapshot: Path, checkpoint: dict[str, Any] | None) -> bool:
    if checkpoint is None or checkpoint["cursor"] == 0:
        return True
    conn = sqlite3.connect(snapshot.resolve().as_uri() + "?mode=ro", uri=True, timeout=10)
    try:
        conn.execute("PRAGMA query_only=ON")
        row = conn.execute(
            "SELECT content_sha256 FROM observations WHERE record_key=?",
            (checkpoint["last_acked_record_key"],),
        ).fetchone()
        if row is None or row[0] != checkpoint["last_acked_content_sha256"]:
            raise BdrMirrorVerificationError("checkpoint_identity_missing_or_conflicting")
        return True
    finally:
        conn.close()


def _source_footprint(path: Path) -> int:
    return sum((Path(str(path) + suffix).stat().st_size
                if Path(str(path) + suffix).exists() else 0)
               for suffix in ("", "-wal", "-shm"))


def _private_new_directory(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise BdrMirrorVerificationError("mirror_output_already_exists")
    path.mkdir(mode=0o700, parents=False)
    os.chmod(path, 0o700)


def _snapshot_live_sqlite(source_path: Path, snapshot_path: Path) -> None:
    if not source_path.is_file() or source_path.name != SOURCE_NAME:
        raise BdrMirrorVerificationError("invalid_incremental_source")
    if source_path.resolve() == snapshot_path.resolve():
        raise BdrMirrorVerificationError("source_and_snapshot_overlap")
    if snapshot_path.exists() or snapshot_path.is_symlink():
        raise BdrMirrorVerificationError("snapshot_already_exists")
    # This is a consistent SQLite snapshot even with a WAL writer active.
    # Never copy just the .sqlite3 file from a live WAL database.
    src = sqlite3.connect(f"file:{source_path.resolve()}?mode=ro", uri=True, timeout=10)
    try:
        src.execute("PRAGMA query_only=ON")
        dst = sqlite3.connect(str(snapshot_path), timeout=10)
        try:
            src.backup(dst, pages=64, sleep=0.05)
            result = dst.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise BdrMirrorVerificationError("sqlite_snapshot_integrity_failed")
        finally:
            dst.close()
    finally:
        src.close()
    os.chmod(snapshot_path, 0o600)


def _canonical_manifest(snapshot_path: Path, bdr: BdrExternalEpisodeCandidate, *,
                        max_records: int) -> tuple[int, str]:
    digest = sha256()
    count = 0
    conn = sqlite3.connect(f"file:{snapshot_path.resolve()}?mode=ro", uri=True, timeout=10)
    try:
        conn.execute("PRAGMA query_only=ON")
        for key, content_sha, source_text in conn.execute(
            "SELECT record_key,content_sha256,source_json FROM observations ORDER BY rowid"
        ):
            if count >= max_records:
                raise BdrMirrorVerificationError("snapshot_exceeds_record_limit")
            if not isinstance(key, str) or not isinstance(content_sha, str) or not isinstance(source_text, str):
                raise BdrMirrorVerificationError("invalid_source_row")
            raw = source_text.encode("utf-8")
            if (bdr._db.get(_seq_key(count)) != key.encode("ascii") or
                    bdr._db.get(_id_key(key)) != raw or
                    sha256(raw).hexdigest() != content_sha):
                raise BdrMirrorVerificationError("bdr_source_mismatch")
            # Length-delimited hashing preserves deterministic source ordering.
            for field in (key.encode("ascii"), content_sha.encode("ascii"), raw):
                digest.update(len(field).to_bytes(4, "big"))
                digest.update(field)
            count += 1
    finally:
        conn.close()
    return count, digest.hexdigest()


def create_verified_mirror(
    source_path: str | Path,
    output_directory: str | Path,
    *,
    library_path: str | Path,
    max_records: int = MAX_RECORDS,
    checkpoint_path: str | Path | None = None,
) -> dict[str, Any]:
    """One run, new private output only. Exceptions leave evidence for diagnosis."""
    if isinstance(max_records, bool) or not isinstance(max_records, int) or not 1 <= max_records <= MAX_RECORDS:
        raise BdrMirrorVerificationError("invalid_max_records")
    if Path(source_path).is_symlink():
        raise BdrMirrorVerificationError("source_symlink")
    source = Path(source_path).resolve()
    output = Path(output_directory)
    native = Path(library_path).resolve()
    if not native.is_file():
        raise BdrMirrorVerificationError("native_bdr_missing")
    if not output.parent.is_dir() or output.parent.is_symlink():
        raise BdrMirrorVerificationError("output_parent_not_available")
    if _source_footprint(source) > MAX_SOURCE_BYTES:
        raise BdrMirrorVerificationError("source_exceeds_space_budget")
    if shutil.disk_usage(output.parent).free < 2 * MAX_SOURCE_BYTES:
        raise BdrMirrorVerificationError("insufficient_mirror_space")
    checkpoint_file = Path(checkpoint_path) if checkpoint_path is not None else None
    checkpoint_before, watermark = _read_checkpoint(checkpoint_file)
    source_inode = source.stat().st_ino
    # In particular, avoid opening the production journal as the destination.
    if output.resolve() == source or source.is_relative_to(output.resolve()):
        raise BdrMirrorVerificationError("output_overlaps_source")
    _private_new_directory(output)
    snapshot = output / SOURCE_NAME
    begin = monotonic()
    _snapshot_live_sqlite(source, snapshot)
    _checkpoint_in_snapshot(snapshot, watermark)
    snap_elapsed = monotonic() - begin
    source_store = IncrementalExternalEpisodeStore(output)
    bdr_root = output / "bdr-candidate"
    bdr = None
    try:
        if source_store.count > max_records:
            raise BdrMirrorVerificationError("snapshot_exceeds_record_limit")
        begin = monotonic()
        bdr = BdrExternalEpisodeCandidate(bdr_root, library_path=native)
        inserted = bdr.mirror_sqlite_snapshot(snapshot)
        assert_count = bdr.count
        if inserted != source_store.count or assert_count != source_store.count:
            raise BdrMirrorVerificationError("initial_import_count_mismatch")
        source_hash = _edge_digest(source_store.core)
        if source_hash != _edge_digest(bdr.core):
            raise BdrMirrorVerificationError("initial_evidence_graph_mismatch")
        count, source_manifest = _canonical_manifest(snapshot, bdr, max_records=max_records)
        if count != assert_count:
            raise BdrMirrorVerificationError("record_manifest_count_mismatch")
        sequence_before = bdr._db.last_sequence()
        if bdr.mirror_sqlite_snapshot(snapshot) != 0:
            raise BdrMirrorVerificationError("non_idempotent_second_mirror")
        if bdr._db.last_sequence() != sequence_before:
            raise BdrMirrorVerificationError("duplicate_advanced_native_sequence")
        bdr.close()
        bdr = None
        recovered = BdrExternalEpisodeCandidate(bdr_root, library_path=native)
        try:
            if recovered.count != count or _edge_digest(recovered.core) != source_hash:
                raise BdrMirrorVerificationError("cold_recovery_graph_mismatch")
            if recovered._db.last_sequence() != recovered._db.durable_sequence():
                raise BdrMirrorVerificationError("cold_recovery_nondurable_sequence")
            manifest_count, recovered_manifest = _canonical_manifest(
                snapshot, recovered, max_records=max_records,
            )
            if manifest_count != count or recovered_manifest != source_manifest:
                raise BdrMirrorVerificationError("cold_recovery_source_mismatch")
            bdr_sequence = recovered._db.durable_sequence()
        finally:
            recovered.close()
        mirror_elapsed = monotonic() - begin
    finally:
        if bdr is not None:
            bdr.close()
        source_store.close()

    checkpoint_after, _ = _read_checkpoint(checkpoint_file)
    report = {
        "schema": REPORT_SCHEMA,
        "checkpoint_watermark_present": _checkpoint_in_snapshot(snapshot, watermark),
        "checkpoint_unchanged_during_copy": checkpoint_before == checkpoint_after,
        "checkpoint_cursor_at_start": watermark["cursor"] if watermark is not None else None,
        "sqlite_source_inode_unchanged": source_inode == source.stat().st_ino,
        "source_mode": "sqlite-online-backup-read-only",
        "source_snapshot_records": count,
        "inserted_into_bdr": inserted,
        "record_manifest_sha256": source_manifest,
        "evidence_graph_sha256": source_hash,
        "bdr_durable_sequence": bdr_sequence,
        "snapshot_seconds": round(snap_elapsed, 4),
        "mirror_and_replay_seconds": round(mirror_elapsed, 4),
        "sqlite_snapshot_bytes": _file_size(output) - _file_size(bdr_root),
        "bdr_candidate_bytes": _file_size(bdr_root),
        "verified_cold_restart": True,
        "verified_idempotent_replay": True,
        "backend_cutover": False,
        "production_checkpoint_advanced": False,
        "world_mutated": False,
        "central_sync": False,
    }
    data = (json.dumps(report, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    report_path = output / "report.json"
    fd = os.open(report_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as destination:
        destination.write(data)
        destination.flush()
        os.fsync(destination.fileno())
    return report
