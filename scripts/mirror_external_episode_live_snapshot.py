#!/usr/bin/env python3
"""Read-only live SQLite snapshot -> private BDR candidate with V2 parity.

Observational experiment only: does not touch the world ledger, checkpoint,
production SQLite database, service config, or runtime APIs. SQLite's backup
API captures a consistent image even when local ingestion stays active.
All copied episode data stays in a mode-0700 private output directory.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
import time
from typing import Any

from memoria_resolutiva.evidence_core import EvidenceCore
from memoria_resolutiva.external_episode_bdr_candidate import (
    BdrExternalEpisodeCandidate, _id_key, _seq_key,
)
from memoria_resolutiva.external_episode_contract import ExternalEpisodeRequest
from memoria_resolutiva.external_episode_incremental import (
    IncrementalEpisodeError, IncrementalExternalEpisodeStore, validated_payload,
)

MAX_SOURCE_BYTES = 256 * 1024 * 1024
MAX_EPISODES = 200_000
MAX_CHECKPOINT_BYTES = 8192
REPORT_SCHEMA = "memoria-v2-bdr-live-snapshot-parity/v1"


def _filesize(path: Path) -> int:
    try:
        return path.stat().st_size
    except FileNotFoundError:
        return 0


def _size(root: Path) -> int:
    return sum(p.stat().st_size for p in root.rglob("*") if p.is_file())


def _source_footprint(source: Path) -> int:
    return sum(_filesize(Path(str(source) + suffix)) for suffix in ("", "-wal", "-shm"))


def _read_checkpoint(path: Path | None) -> tuple[bytes | None, dict[str, Any] | None]:
    if path is None:
        return None, None
    if path.is_symlink():
        raise IncrementalEpisodeError("checkpoint is a symlink")
    with path.open("rb") as fh:
        raw = fh.read(MAX_CHECKPOINT_BYTES + 1)
    if len(raw) > MAX_CHECKPOINT_BYTES:
        raise IncrementalEpisodeError("checkpoint exceeds read limit")
    try:
        decoded = json.loads(raw)
    except ValueError as exc:
        raise IncrementalEpisodeError("checkpoint invalid JSON") from exc
    if not isinstance(decoded, dict) or decoded.get("schema") != "live-infinita-nov-local-memory-checkpoint/v1":
        raise IncrementalEpisodeError("checkpoint schema mismatch")
    if not isinstance(decoded.get("cursor"), int) or isinstance(decoded["cursor"], bool) or decoded["cursor"] < 0:
        raise IncrementalEpisodeError("checkpoint cursor invalid")
    key, digest = decoded.get("last_acked_record_key"), decoded.get("last_acked_content_sha256")
    if not (isinstance(key, str) and isinstance(digest, str) and len(key) == 64 and len(digest) == 64):
        raise IncrementalEpisodeError("checkpoint last acknowledged identity missing")
    if not all(c in "0123456789abcdef" for c in key + digest):
        raise IncrementalEpisodeError("checkpoint identity malformed")
    return raw, decoded


def _snapshot_sqlite(source: Path, snapshot: Path) -> None:
    """Copy one committed WAL-consistent image without writer interruption."""
    if source.is_symlink() or not source.is_file():
        raise IncrementalEpisodeError("SQLite source missing or symlinked")
    if _source_footprint(source) > MAX_SOURCE_BYTES:
        raise IncrementalEpisodeError("source exceeds snapshot safety budget")
    uri = source.resolve().as_uri() + "?mode=ro"
    readonly = sqlite3.connect(uri, uri=True, timeout=5, isolation_level=None)
    destination = sqlite3.connect(snapshot, timeout=5, isolation_level=None)
    try:
        readonly.execute("PRAGMA query_only=ON")
        readonly.backup(destination, pages=128, sleep=0.025)
        result = destination.execute("PRAGMA integrity_check").fetchone()
        if result != ("ok",):
            raise IncrementalEpisodeError("SQLite backup integrity check failed")
    finally:
        destination.close()
        readonly.close()
    os.chmod(snapshot, 0o600)


def _edges(core: EvidenceCore) -> tuple:
    return tuple(
        (e.subject, e.predicate, e.object, e.evidence_id, e.source_text,
         e.namespace, e.epoch, e.provenance, e.origin, e.confidence)
        for e in core._edges
    )


def _verify_snapshot(snapshot: Path, bdr: BdrExternalEpisodeCandidate,
                     checkpoint: dict[str, Any] | None) -> dict[str, Any]:
    connection = sqlite3.connect(
        snapshot.resolve().as_uri() + "?mode=ro", uri=True, isolation_level=None
    )
    expected_graph = EvidenceCore()
    prefix = sha256()
    count = 0
    ack_found = checkpoint is None
    try:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            "SELECT record_key,content_sha256,source_json,evidence_id,world_id,"
            "episode_id,logical_tick FROM observations ORDER BY rowid"
        )
        for key, digest, source, evidence_id, world_id, episode_id, tick in rows:
            if count >= MAX_EPISODES:
                raise IncrementalEpisodeError("snapshot exceeds observation limit")
            if not isinstance(source, str) or len(source.encode("utf-8")) > 8192:
                raise IncrementalEpisodeError("snapshot observation payload invalid")
            try:
                unsigned = json.loads(source)
                request = ExternalEpisodeRequest.model_validate({
                    **unsigned, "content_sha256": digest,
                })
                expected_key, payload, expected_digest, expected_eid = validated_payload(request)
            except (TypeError, ValueError, UnicodeError) as exc:
                raise IncrementalEpisodeError("snapshot source contract invalid") from exc
            if (key != expected_key or digest != expected_digest or
                source != payload.decode("utf-8") or evidence_id != expected_eid or
                world_id != request.source.world_id or episode_id != request.source.episode_id or
                tick != request.observation.logical_tick):
                raise IncrementalEpisodeError("snapshot source/index mismatch")
            if bdr._db.get(_seq_key(count)) != key.encode("ascii"):
                raise IncrementalEpisodeError("BDR sequence index mismatch")
            if bdr._db.get(_id_key(key)) != payload:
                raise IncrementalEpisodeError("BDR canonical payload mismatch")
            IncrementalExternalEpisodeStore._observe_core(expected_graph, request, expected_eid, payload)
            prefix.update(len(payload).to_bytes(8, "big"))
            prefix.update(payload)
            count += 1
            if checkpoint is not None and key == checkpoint["last_acked_record_key"]:
                if digest != checkpoint["last_acked_content_sha256"]:
                    raise IncrementalEpisodeError("checkpoint digest conflicts with snapshot")
                ack_found = True
        if count != bdr.count:
            raise IncrementalEpisodeError("BDR count mismatch")
        if not ack_found:
            raise IncrementalEpisodeError("checkpoint identity absent from SQLite snapshot")
        if _edges(expected_graph) != _edges(bdr.core):
            raise IncrementalEpisodeError("EvidenceCore projection mismatch")
        if bdr._db.durable_sequence() != bdr._db.last_sequence():
            raise IncrementalEpisodeError("BDR contains non-durable sequence")
        return {"observations": count, "stream_sha256": prefix.hexdigest(),
                "checkpoint_ref_present": ack_found}
    finally:
        connection.close()


def mirror_live_snapshot(
    source: Path, output: Path, *, library_path: Path,
    checkpoint_path: Path | None = None,
) -> dict[str, Any]:
    """Create a private, non-authoritative BDR mirror from a live SQLite source."""
    source, output, library_path = Path(source), Path(output), Path(library_path)
    if output.exists() or output.is_symlink():
        raise IncrementalEpisodeError("mirror destination must not exist")
    if not library_path.is_file() or library_path.is_symlink():
        raise IncrementalEpisodeError("explicit native BDR library is required")
    if not source.is_file() or source.is_symlink():
        raise IncrementalEpisodeError("production SQLite source invalid")
    available = shutil.disk_usage(output.parent).free
    if available < 3 * MAX_SOURCE_BYTES:
        raise IncrementalEpisodeError("insufficient free space for bounded private mirror")
    checkpoint_before, checkpoint = _read_checkpoint(checkpoint_path)
    previous_stat = source.stat()
    if previous_stat.st_size > MAX_SOURCE_BYTES:
        raise IncrementalEpisodeError("source exceeds mirror safety budget")
    old_umask = os.umask(0o077)
    try:
        output.mkdir(mode=0o700)
    finally:
        os.umask(old_umask)
    snapshot = output / "sqlite-snapshot.sqlite3"
    bdr_root = output / "bdr"
    candidate = None
    start = time.monotonic()
    try:
        _snapshot_sqlite(source, snapshot)
        backup_stat = snapshot.stat()
        if backup_stat.st_size > MAX_SOURCE_BYTES:
            raise IncrementalEpisodeError("backup exceeds mirror safety budget")
        candidate = BdrExternalEpisodeCandidate(bdr_root, library_path=library_path)
        imported = candidate.mirror_sqlite_snapshot(snapshot)
        verification = _verify_snapshot(snapshot, candidate, checkpoint)
        if imported != verification["observations"]:
            raise IncrementalEpisodeError("unexpected imported count; destination not empty")
        candidate.close()
        candidate = None
        reopened = BdrExternalEpisodeCandidate(bdr_root, library_path=library_path)
        try:
            after_reopen = _verify_snapshot(snapshot, reopened, checkpoint)
        finally:
            reopened.close()
        if after_reopen != verification:
            raise IncrementalEpisodeError("cold replay changed parity")
        after_checkpoint, _ = _read_checkpoint(checkpoint_path)
        report = {
            "schema": REPORT_SCHEMA,
            "mode": "read-only-snapshot-and-private-bdr-candidate",
            "source_is_authoritative": True,
            "bdr_is_authoritative": False,
            "source_count": verification["observations"],
            "bdr_count": verification["observations"],
            "source_stream_sha256": verification["stream_sha256"],
            "bdr_stream_sha256": after_reopen["stream_sha256"],
            "checkpoint_ref_present_at_snapshot": verification["checkpoint_ref_present"],
            "checkpoint_unchanged_during_mirror": checkpoint_before == after_checkpoint,
            "sqlite_source_inode_unchanged": previous_stat.st_ino == source.stat().st_ino,
            "snapshot_bytes": _size(output) - _size(bdr_root),
            "bdr_bytes": _size(bdr_root),
            "elapsed_seconds": round(time.monotonic() - start, 3),
            "world_mutated": False,
            "checkpoint_advanced": False,
            "production_sqlite_modified_by_mirror": False,
            "backend_switched": False,
        }
        report_file = output / "parity-report.json"
        fd = os.open(report_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(output, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return report
    finally:
        if candidate is not None:
            candidate.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Private, read-only SQLite -> native BDR parity mirror")
    parser.add_argument("--sqlite-source", type=Path, required=True)
    parser.add_argument("--bdr-library", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="A NEW private directory; never production SQLite/BDR root")
    parser.add_argument("--checkpoint", type=Path, default=None)
    args = parser.parse_args()
    try:
        report = mirror_live_snapshot(
            args.sqlite_source, args.output,
            library_path=args.bdr_library, checkpoint_path=args.checkpoint,
        )
    except (IncrementalEpisodeError, OSError, sqlite3.Error) as exc:
        raise SystemExit("BDR_MIRROR_BLOCKED " + type(exc).__name__ + ": " + str(exc)) from exc
    print("BDR_MIRROR_PARITY_OK " + json.dumps(report, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
