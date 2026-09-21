from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from threading import RLock
from typing import Any

from .bdr_store import BDRResolutiveMemory
from .sqlite_store import SQLiteResolutiveMemory
from .storage_backend import open_resolutive_memory


STRUCTURAL_OBSERVATION_FORMAT = "memoria.ia-structural-observation-v1"
STRUCTURAL_INDEX_FORMAT = "memoria.ia-structural-observation-index-v1"

_EVENT_FIELDS = (
    "version",
    "source_id",
    "sequence",
    "byte_offset",
    "byte_length",
    "trail",
    "relation_ids",
    "signature",
    "resolution",
)


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _normalize_event(event: dict[str, Any]) -> dict[str, Any]:
    missing = [field for field in _EVENT_FIELDS if field not in event]
    if missing:
        raise ValueError("missing StructuralEvent fields: " + ", ".join(missing))

    normalized = {
        "version": int(event["version"]),
        "source_id": str(event["source_id"]).strip(),
        "sequence": int(event["sequence"]),
        "byte_offset": int(event["byte_offset"]),
        "byte_length": int(event["byte_length"]),
        "trail": [int(item) for item in event["trail"]],
        "relation_ids": [int(item) for item in event["relation_ids"]],
        "signature": str(event["signature"]).strip().lower(),
        "resolution": int(event["resolution"]),
    }
    if normalized["version"] < 1:
        raise ValueError("StructuralEvent version must be >= 1")
    if not normalized["source_id"]:
        raise ValueError("StructuralEvent source_id must be non-empty")
    if normalized["sequence"] < 0 or normalized["byte_offset"] < 0:
        raise ValueError("StructuralEvent sequence and byte_offset must be >= 0")
    if normalized["byte_length"] <= 0:
        raise ValueError("StructuralEvent byte_length must be > 0")
    if normalized["resolution"] <= 0:
        raise ValueError("StructuralEvent resolution must be > 0")
    if len(normalized["signature"]) != 16 or any(c not in "0123456789abcdef" for c in normalized["signature"]):
        raise ValueError("StructuralEvent signature must be a 16-character hexadecimal digest")
    if any(item < 0 for item in normalized["trail"]):
        raise ValueError("StructuralEvent trail ids must be >= 0")
    if any(item < 0 for item in normalized["relation_ids"]):
        raise ValueError("StructuralEvent relation ids must be >= 0")
    return normalized


@dataclass(frozen=True, slots=True)
class StructuralObservationReceipt:
    backend: str
    state_id: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "backend": self.backend,
            "state_id": self.state_id,
            "sha256": self.sha256,
        }


class StructuralObservationPersistence:
    """Content-addressed persistence for raw structural observations.

    This layer deliberately stores the complete observation envelope without
    mapping symbols to semantic predicates. BDR/SQLite provide durability only;
    interpretation remains a later, evidence-driven stage.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        backend: str | None = None,
        allow_fallback: bool = True,
    ) -> None:
        self.root = Path(root)
        self.backend = backend
        self.allow_fallback = allow_fallback
        self.last_backend: str | None = None

    @staticmethod
    def _backend_name(store: object) -> str:
        if isinstance(store, BDRResolutiveMemory):
            return "bdr"
        if isinstance(store, SQLiteResolutiveMemory):
            return "sqlite"
        return type(store).__name__.lower()

    def _open(self, *, backend: str | None = None, allow_fallback: bool | None = None):
        store = open_resolutive_memory(
            self.root,
            backend=self.backend if backend is None else backend,
            allow_fallback=self.allow_fallback if allow_fallback is None else allow_fallback,
        )
        self.last_backend = self._backend_name(store)
        return store

    def store(self, payload: bytes) -> StructuralObservationReceipt:
        digest = hashlib.sha256(payload).hexdigest()
        state_id = f"structural-observation:{digest}"
        store = self._open()
        backend_name = self._backend_name(store)
        try:
            try:
                existing = store.reconstruct(state_id)
            except KeyError:
                existing = None
            if existing is None:
                store.add(state_id, payload)
            elif existing != payload:
                raise ValueError("structural observation content-address collision")
        finally:
            store.close()
        return StructuralObservationReceipt(backend_name, state_id, digest)

    def load(self, receipt: StructuralObservationReceipt | dict[str, str]) -> bytes:
        if isinstance(receipt, StructuralObservationReceipt):
            backend = receipt.backend
            state_id = receipt.state_id
            expected = receipt.sha256
        else:
            backend = str(receipt["backend"])
            state_id = str(receipt["state_id"])
            expected = str(receipt["sha256"])
        store = self._open(backend=backend, allow_fallback=False)
        try:
            payload = store.reconstruct(state_id)
        finally:
            store.close()
        actual = hashlib.sha256(payload).hexdigest()
        if actual != expected:
            raise ValueError("structural observation persistence checksum mismatch")
        return payload


class StructuralObservationStore:
    """Append-only intake for bit.analyze StructuralEvent observations.

    Identity is derived only from the StructuralEvent itself. Provenance metadata
    is preserved in the immutable envelope but does not participate in semantic
    interpretation. Replaying the exact same event is idempotent.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        backend: str | None = None,
        allow_fallback: bool = True,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.persistence = StructuralObservationPersistence(
            self.root / "persistence",
            backend=backend,
            allow_fallback=allow_fallback,
        )
        self.index_path = self.root / "index.jsonl"
        self._lock = RLock()
        self._entries: dict[str, dict[str, Any]] = {}
        self._order: list[str] = []
        self._load_index()

    def _load_index(self) -> None:
        if not self.index_path.exists():
            return
        for line_number, line in enumerate(self.index_path.read_text("utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("format") != STRUCTURAL_INDEX_FORMAT:
                raise ValueError(f"unsupported structural observation index at line {line_number}")
            observation_id = str(row.get("observation_id") or "")
            if not observation_id:
                raise ValueError(f"missing observation_id at line {line_number}")
            receipt = row.get("receipt")
            if not isinstance(receipt, dict):
                raise ValueError(f"invalid structural observation receipt at line {line_number}")
            existing = self._entries.get(observation_id)
            if existing is not None:
                if existing != row:
                    raise ValueError("conflicting duplicate structural observation index entry")
                continue
            self._entries[observation_id] = row
            self._order.append(observation_id)

    @staticmethod
    def observation_id(event: dict[str, Any]) -> str:
        normalized = _normalize_event(event)
        digest = hashlib.blake2b(_canonical_json(normalized), digest_size=20).hexdigest()
        return "structural-event:" + digest

    @property
    def count(self) -> int:
        return len(self._order)

    @property
    def backend(self) -> str:
        return self.persistence.last_backend or self.persistence.backend or "auto"

    def append(
        self,
        event: dict[str, Any],
        *,
        provenance: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], bool]:
        normalized = _normalize_event(event)
        observation_id = self.observation_id(normalized)
        envelope = {
            "format": STRUCTURAL_OBSERVATION_FORMAT,
            "observation_id": observation_id,
            "event": normalized,
            "provenance": {} if provenance is None else provenance,
            "semantic_projection": False,
        }
        payload = _canonical_json(envelope)

        with self._lock:
            existing = self._entries.get(observation_id)
            if existing is not None:
                stored = self.get(observation_id)
                if _canonical_json(stored) != payload:
                    raise ValueError("same StructuralEvent arrived with conflicting provenance")
                return stored, True

            receipt = self.persistence.store(payload)
            row = {
                "format": STRUCTURAL_INDEX_FORMAT,
                "observation_id": observation_id,
                "receipt": receipt.as_dict(),
            }
            with self.index_path.open("a", encoding="utf-8", newline="\n") as fh:
                fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            self._entries[observation_id] = row
            self._order.append(observation_id)
            return envelope, False

    def get(self, observation_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._entries.get(observation_id)
            if row is None:
                raise KeyError(observation_id)
            payload = self.persistence.load(row["receipt"])
        envelope = json.loads(payload.decode("utf-8"))
        if envelope.get("format") != STRUCTURAL_OBSERVATION_FORMAT:
            raise ValueError("unsupported structural observation format")
        if envelope.get("observation_id") != observation_id:
            raise ValueError("structural observation identity mismatch")
        return envelope

    def recent(self, limit: int = 20) -> tuple[dict[str, Any], ...]:
        if limit < 1:
            raise ValueError("limit must be >= 1")
        ids = tuple(self._order[-limit:])
        return tuple(self.get(observation_id) for observation_id in ids)
