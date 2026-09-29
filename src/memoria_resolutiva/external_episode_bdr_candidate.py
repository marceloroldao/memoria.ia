"""Experimental BDR v1.2 Atomic C ABI journal for V2 observed episodes.

NOT wired into ProductServer or any production mode. This is a parity/durability
candidate to compare to the current SQLite incremental implementation. It
stores a canonical envelope once and indexes it by full identity and sequence.
All three keys are one *durable native BDR atomic batch*; no full-core snapshot.
"""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any

from .evidence_core import EvidenceCore
from .external_episode_contract import ExternalEpisodeRequest
from .external_episode_incremental import (
    IncrementalEpisodeError, IncrementalExternalEpisodeStore, validated_payload,
)

FORMAT = b"memoria-v2-external-episode-bdr-candidate/v1"
COUNT = "external:v1:count"
MARKER = "external:v1:format"
MAX_RECORDS = 10**12
MAX_READ_BATCH = 256


def _id_key(key: str) -> str:
    return "external:v1:id:" + key


def _seq_key(seq: int) -> str:
    return f"external:v1:seq:{seq:016d}"


class BdrExternalEpisodeCandidate:
    """One deterministic owner; BDR native library and path are explicit."""

    def __init__(self, root: str | Path, *, library_path: str | Path):
        # A missing native library is a hard error, never a silent SQLite fallback.
        from bdr.atomic import AtomicBDR
        if not library_path or not Path(library_path).is_file():
            raise IncrementalEpisodeError("pinned native BDR library not available")
        self.path = Path(root)
        self.path.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._poisoned = False
        self._db = AtomicBDR.open(self.path, library_path=library_path)
        self.core = EvidenceCore()
        try:
            self._count = self._load_count()
            self._rehydrate()
        except BaseException:
            self._db.close()
            raise

    def _load_count(self) -> int:
        value = self._db.get(COUNT)
        marker = self._db.get(MARKER)
        if value is None:
            if marker is not None or self._db.last_sequence() != 0:
                raise IncrementalEpisodeError("BDR candidate metadata missing")
            return 0
        if marker != FORMAT or not value or not value.isascii() or not value.isdigit():
            raise IncrementalEpisodeError("BDR candidate metadata corrupt")
        count = int(value)
        if not 0 <= count <= MAX_RECORDS:
            raise IncrementalEpisodeError("BDR candidate count invalid")
        if self._db.durable_sequence() < self._db.last_sequence():
            raise IncrementalEpisodeError("BDR contains unacknowledged sequence")
        return count

    def _decode(self, key: str, payload: bytes, seq: int) -> ExternalEpisodeRequest:
        if len(payload) > 8192:
            raise IncrementalEpisodeError("BDR candidate oversized observation")
        try:
            unsigned = json.loads(payload)
            request = ExternalEpisodeRequest.model_validate({
                **unsigned, "content_sha256": sha256(payload).hexdigest(),
            })
            expected_key, canonical_payload, _digest, eid = validated_payload(request)
        except (ValueError, TypeError, UnicodeError) as exc:
            raise IncrementalEpisodeError("BDR candidate corrupt observation") from exc
        if key != expected_key or payload != canonical_payload:
            raise IncrementalEpisodeError("BDR candidate observation/index mismatch")
        if self._db.get(_id_key(key)) != payload:
            raise IncrementalEpisodeError("BDR candidate identity index mismatch")
        IncrementalExternalEpisodeStore._observe_core(
            self.core, request, eid, canonical_payload,
        )
        return request

    def _rehydrate(self) -> None:
        count = 0
        for offset in range(0, self._count, MAX_READ_BATCH):
            indexes = list(range(offset, min(offset + MAX_READ_BATCH, self._count)))
            raw_keys = self._db.get_many([_seq_key(i) for i in indexes])
            if len(raw_keys) != len(indexes):
                raise IncrementalEpisodeError("BDR candidate incomplete sequence index")
            for idx, raw in zip(indexes, raw_keys):
                try:
                    key = raw.decode("ascii") if raw is not None else ""
                except (UnicodeError, AttributeError) as exc:
                    raise IncrementalEpisodeError("BDR candidate invalid index") from exc
                if len(key) != 64 or not all(c in "0123456789abcdef" for c in key):
                    raise IncrementalEpisodeError("BDR candidate missing/corrupt sequence")
                payload = self._db.get(_id_key(key))
                if payload is None:
                    raise IncrementalEpisodeError("BDR candidate missing observation")
                self._decode(key, payload, idx)
                count += 1
        if count != self._count:
            raise IncrementalEpisodeError("BDR candidate count mismatch")

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    def observe(self, request: ExternalEpisodeRequest) -> dict[str, Any]:
        from bdr.atomic import DurabilityMode
        key, payload, digest, evidence_id = validated_payload(request)
        source = request.source
        with self._lock:
            if self._poisoned:
                raise RuntimeError("BDR candidate requires restart")
            existing = self._db.get(_id_key(key))
            if existing is not None:
                if existing != payload:
                    raise IncrementalEpisodeError("episode identity reused with different observed content")
                stored = False
            else:
                sequence = self._count
                operations = [
                    (_id_key(key), payload),
                    (_seq_key(sequence), key.encode("ascii")),
                    (COUNT, str(sequence + 1).encode("ascii")),
                ]
                if sequence == 0:
                    operations.append((MARKER, FORMAT))
                # A single transaction groups data, identity index and count.
                # Never ACK BATCH_SYNC only by successful return: check native
                # durable sequence to prevent false durability claims.
                try:
                    result = self._db.put_many(operations, durability=DurabilityMode.BATCH_SYNC)
                    if (not result.durable or result.operations != len(operations)
                        or self._db.durable_sequence() < result.sequence):
                        self._poisoned = True
                        raise RuntimeError("BDR atomic durability not confirmed")
                    IncrementalExternalEpisodeStore._observe_core(
                        self.core, request, evidence_id, payload,
                    )
                except BaseException:
                    self._poisoned = True
                    raise
                self._count += 1
                stored = True
            return {
                "schema": "live-infinita-npc-episode-observation/v1",
                "ack": True,
                "stored": stored,
                "record_key": key,
                "episode_id": source.episode_id,
                "evidence_id": evidence_id,
                "content_sha256": digest,
                "world_id": source.world_id,
                "persistence": {
                    "backend": "bdr-incremental-candidate",
                    "state_id": "external-episode:" + key,
                    "sha256": digest,
                    "durable_sequence": self._db.durable_sequence(),
                },
                "world_mutated": False,
                "selection_authority": False,
            }

    def mirror_sqlite_snapshot(self, sqlite_path: Path) -> int:
        """Side-by-side *copy*, never switches production or edits SQLite.

        Requires the source to be quiescent. Every row is validated using the
        current real V2 canonical request and digest before receiving an ACK.
        """
        source = sqlite3.connect(
            f"file:{Path(sqlite_path).resolve()}?mode=ro", uri=True, timeout=5,
        )
        imported = 0
        try:
            source.execute("PRAGMA query_only=ON")
            source.execute("BEGIN")
            for record_key, digest, payload in source.execute(
                "SELECT record_key,content_sha256,source_json FROM observations ORDER BY rowid"
            ):
                try:
                    unsigned = json.loads(payload)
                    request = ExternalEpisodeRequest.model_validate({
                        **unsigned, "content_sha256": digest,
                    })
                    key, original, original_digest, _ = validated_payload(request)
                except (TypeError, ValueError, UnicodeError) as exc:
                    raise IncrementalEpisodeError("invalid SQLite mirror source") from exc
                if key != record_key or original_digest != digest or original.decode("utf-8") != payload:
                    raise IncrementalEpisodeError("SQLite mirror source mismatch")
                imported += int(self.observe(request)["stored"])
            source.execute("COMMIT")
        except BaseException:
            source.execute("ROLLBACK")
            raise
        finally:
            source.close()
        return imported

    def close(self) -> None:
        with self._lock:
            self._db.close()
