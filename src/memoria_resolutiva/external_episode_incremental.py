"""Incremental durable journal for typed external episodes in genuine V2 EvidenceCore.

This is an opt-in *storage backend*, not an independent inference engine.
Each acknowledged observation is a single atomic SQLite WAL transaction.
The real EvidenceCore is rehydrated and validated from canonical source rows.
"""
from __future__ import annotations

from hashlib import sha256
import hmac
import json
from pathlib import Path
import sqlite3
from threading import RLock

from .evidence_core import EvidenceCore
from .external_episode_contract import ExternalEpisodeRequest, FORMAT, PROVENANCE, canonical

MAX_ENVELOPE_BYTES = 8192
SCHEMA = "memoria-v2-incremental-external-episode/v1"


class IncrementalEpisodeError(ValueError):
    pass


def validated_payload(request: ExternalEpisodeRequest) -> tuple[str, bytes, str, str]:
    source = request.source
    if source.episode_id != "plan:" + source.plan_id:
        raise IncrementalEpisodeError("episode plan provenance mismatch")
    identity = {
        "system": source.system, "world_id": source.world_id,
        "entity_id": source.entity_id, "episode_id": source.episode_id,
    }
    key = sha256(canonical(identity)).hexdigest()
    if not hmac.compare_digest(key, request.record_key):
        raise IncrementalEpisodeError("record identity mismatch")
    unsigned = request.model_dump(mode="json", exclude={"content_sha256"})
    payload = canonical(unsigned)
    if len(payload) > MAX_ENVELOPE_BYTES:
        raise IncrementalEpisodeError("episode exceeds incremental journal limit")
    digest = sha256(payload).hexdigest()
    if not hmac.compare_digest(digest, request.content_sha256):
        raise IncrementalEpisodeError("observation digest mismatch")
    return key, payload, digest, "live-obs:" + key[:40]


class IncrementalExternalEpisodeStore:
    """Single writer, immutable source rows, in-memory genuine EvidenceCore."""

    def __init__(self, root: str | Path):
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "external-episodes.sqlite3"
        self._lock = RLock()
        self._poisoned = False
        self._db = sqlite3.connect(self.path, timeout=10, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("PRAGMA synchronous=FULL")
        self._db.execute("PRAGMA foreign_keys=ON")
        self._db.execute("PRAGMA busy_timeout=10000")
        self._db.execute("""
            CREATE TABLE IF NOT EXISTS observations (
                record_key TEXT PRIMARY KEY,
                content_sha256 TEXT NOT NULL,
                source_json TEXT NOT NULL,
                evidence_id TEXT NOT NULL UNIQUE,
                world_id TEXT NOT NULL,
                episode_id TEXT NOT NULL,
                logical_tick INTEGER NOT NULL
            )
        """)
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_external_world_tick ON observations(world_id,logical_tick DESC)")
        self.core = EvidenceCore()
        self._count = 0
        try:
            self._rehydrate()
        except BaseException:
            self._db.close()
            raise

    @staticmethod
    def _observe_core(core: EvidenceCore, request: ExternalEpisodeRequest, evidence_id: str, payload: bytes) -> None:
        source = request.source
        core.observe_relation(
            "live:episode:" + evidence_id, "observed_experience",
            "live:entity:" + source.world_id + ":" + source.entity_id,
            evidence_id=evidence_id,
            source_text=payload.decode("utf-8"),
            provenance=PROVENANCE, origin="live.infinita:" + source.world_id,
            confidence=1.0, namespace="live:" + source.world_id,
            epoch=request.observation.logical_tick,
        )

    def _rehydrate(self) -> None:
        """No derived cache is trusted on restart; validate the whole journal."""
        for key, digest, payload, evidence_id, world_id, episode_id, tick in self._db.execute(
            "SELECT record_key,content_sha256,source_json,evidence_id,world_id,episode_id,logical_tick "
            "FROM observations ORDER BY rowid"
        ):
            if not isinstance(payload, str) or len(payload.encode("utf-8")) > MAX_ENVELOPE_BYTES:
                raise IncrementalEpisodeError("corrupt incremental source length")
            try:
                unsigned = json.loads(payload)
                request = ExternalEpisodeRequest.model_validate({
                    **unsigned, "content_sha256": digest,
                })
                expected_key, expected_payload, expected_digest, expected_evidence = validated_payload(request)
            except (ValueError, TypeError, UnicodeError) as exc:
                raise IncrementalEpisodeError("corrupt incremental observation") from exc
            if (key != expected_key or digest != expected_digest or
                payload != expected_payload.decode("utf-8") or evidence_id != expected_evidence or
                world_id != request.source.world_id or episode_id != request.source.episode_id or
                tick != request.observation.logical_tick):
                raise IncrementalEpisodeError("incremental observation/index mismatch")
            self._observe_core(self.core, request, evidence_id, expected_payload)
            self._count += 1

    @property
    def count(self) -> int:
        with self._lock:
            return self._count

    def observe(self, request: ExternalEpisodeRequest) -> dict:
        key, payload, digest, evidence_id = validated_payload(request)
        source = request.source
        with self._lock:
            if self._poisoned:
                raise RuntimeError("incremental EvidenceCore requires restart")
            row = self._db.execute(
                "SELECT content_sha256,source_json FROM observations WHERE record_key=?", (key,)
            ).fetchone()
            if row is not None:
                if row != (digest, payload.decode("utf-8")):
                    raise IncrementalEpisodeError("episode identity reused with different observed content")
                stored = False
            else:
                # Only the canonical source row is stored; no full-graph snapshot.
                # Durable commit precedes the ACK. A core projection failure
                # poisons this process; restart deterministically rehydrates.
                self._db.execute("BEGIN IMMEDIATE")
                try:
                    self._db.execute(
                        "INSERT INTO observations "
                        "(record_key,content_sha256,source_json,evidence_id,world_id,episode_id,logical_tick) "
                        "VALUES (?,?,?,?,?,?,?)",
                        (key, digest, payload.decode("utf-8"), evidence_id,
                         source.world_id, source.episode_id, request.observation.logical_tick),
                    )
                    self._db.execute("COMMIT")
                except BaseException:
                    self._db.execute("ROLLBACK")
                    raise
                try:
                    self._observe_core(self.core, request, evidence_id, payload)
                except BaseException:
                    self._poisoned = True
                    raise
                self._count += 1
                stored = True
            return {
                "schema": FORMAT, "ack": True, "stored": stored,
                "record_key": key, "episode_id": source.episode_id,
                "evidence_id": evidence_id, "content_sha256": digest,
                "world_id": source.world_id,
                "persistence": {
                    "backend": "sqlite-incremental",
                    "state_id": "external-episode:" + key,
                    "sha256": digest,
                },
                "world_mutated": False, "selection_authority": False,
            }

    def migrate_legacy(self, evidence) -> int:
        """Idempotent bridge of exactly verified legacy external observations.

        Legacy source snapshots and receipt are never removed or overwritten.
        Non-external evidence in the legacy store blocks automatic migration.
        """
        if evidence.receipt is None:
            return 0
        rows = tuple(evidence.core._edges)
        imported = 0
        for edge in rows:
            if edge.provenance != PROVENANCE or edge.predicate != "observed_experience":
                raise IncrementalEpisodeError("legacy evidence includes non-external rows; explicit migration required")
            try:
                unsigned = json.loads(edge.source_text)
                request = ExternalEpisodeRequest.model_validate({
                    **unsigned, "content_sha256": sha256(canonical(unsigned)).hexdigest(),
                })
                key, payload, digest, evidence_id = validated_payload(request)
            except (ValueError, TypeError) as exc:
                raise IncrementalEpisodeError("legacy external evidence provenance invalid") from exc
            source = request.source
            if (
                edge.evidence_id != evidence_id
                or edge.subject != "live:episode:" + evidence_id
                or edge.object != "live:entity:" + source.world_id + ":" + source.entity_id
                or edge.namespace != "live:" + source.world_id
                or edge.origin != "live.infinita:" + source.world_id
                or edge.epoch != request.observation.logical_tick
                or edge.confidence != 1.0
                or edge.source_text != payload.decode("utf-8")
            ):
                raise IncrementalEpisodeError("legacy external evidence disagrees with observation")
            imported += int(self.observe(request)["stored"])
        return imported

    def close(self) -> None:
        with self._lock:
            self._db.close()
