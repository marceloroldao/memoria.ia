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
from .structural_association_field import StructuralAssociationField
from .structural_observation import StructuralObservationStore


RUNTIME_FORMAT = "memoria.ia-structural-association-runtime-v1"
POINTER_FORMAT = "memoria.ia-structural-association-pointer-v1"


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class StructuralAssociationStateReceipt:
    backend: str
    state_id: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "backend": self.backend,
            "state_id": self.state_id,
            "sha256": self.sha256,
        }


class StructuralAssociationPersistence:
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

    def store(self, payload: bytes) -> StructuralAssociationStateReceipt:
        digest = hashlib.sha256(payload).hexdigest()
        state_id = f"structural-association-state:{digest}"
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
                raise ValueError("structural association state id collision")
        finally:
            store.close()
        return StructuralAssociationStateReceipt(backend_name, state_id, digest)

    def load(self, receipt: StructuralAssociationStateReceipt | dict[str, str]) -> bytes:
        if isinstance(receipt, StructuralAssociationStateReceipt):
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
            raise ValueError("structural association state checksum mismatch")
        return payload


class StructuralAssociationRuntime:
    """Durable derived association state over canonical raw observations.

    Raw StructuralObservationStore rows remain authoritative. The derived field
    carries a cursor into that append-only sequence. A crash can therefore leave
    the derived checkpoint behind the raw store, but never requires guessing:
    sync replays exactly the missing suffix and checkpoints the result.
    """

    def __init__(
        self,
        observations: StructuralObservationStore,
        root: str | Path,
        *,
        backend: str | None = None,
        allow_fallback: bool = True,
        max_within_distance: int = 8,
        max_event_lag: int = 4,
        forgetting_rate: float = 0.01,
    ) -> None:
        self.observations = observations
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.pointer_path = self.root / "current.json"
        self.persistence = StructuralAssociationPersistence(
            self.root / "persistence",
            backend=backend,
            allow_fallback=allow_fallback,
        )
        self._lock = RLock()
        self.field = StructuralAssociationField(
            max_within_distance=max_within_distance,
            max_event_lag=max_event_lag,
            forgetting_rate=forgetting_rate,
        )
        self.cursor_count = 0
        self.cursor_observation_id: str | None = None
        self.replayed_on_open = 0
        self._load_if_present()
        self.replayed_on_open = self.sync()

    @staticmethod
    def _parse_cursor(value: object) -> tuple[int, str | None]:
        if not isinstance(value, dict):
            raise ValueError("structural association cursor must be an object")
        count = int(value.get("count", 0))
        if count < 0:
            raise ValueError("structural association cursor count must be >= 0")
        raw_id = value.get("observation_id")
        observation_id = None if raw_id is None else str(raw_id).strip() or None
        if count == 0 and observation_id is not None:
            raise ValueError("empty structural association cursor cannot name an observation")
        if count > 0 and observation_id is None:
            raise ValueError("non-empty structural association cursor requires observation_id")
        return count, observation_id

    def _validate_cursor(self) -> None:
        if self.cursor_count > self.observations.count:
            raise ValueError("structural association cursor is ahead of raw observations")
        if self.cursor_count == 0:
            if self.cursor_observation_id is not None:
                raise ValueError("empty structural association cursor is inconsistent")
            return
        expected = self.observations.observation_id_at(self.cursor_count - 1)
        if expected != self.cursor_observation_id:
            raise ValueError("structural association cursor does not match raw observation prefix")

    def _load_if_present(self) -> None:
        if not self.pointer_path.is_file():
            return
        pointer = json.loads(self.pointer_path.read_text("utf-8"))
        if not isinstance(pointer, dict) or pointer.get("format") != POINTER_FORMAT:
            raise ValueError("unsupported structural association pointer format")
        receipt = pointer.get("receipt")
        if not isinstance(receipt, dict):
            raise ValueError("structural association pointer receipt is invalid")
        payload = json.loads(self.persistence.load(receipt).decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("format") != RUNTIME_FORMAT:
            raise ValueError("unsupported structural association runtime format")
        self.cursor_count, self.cursor_observation_id = self._parse_cursor(payload.get("cursor"))
        field_state = payload.get("field")
        if not isinstance(field_state, dict):
            raise ValueError("structural association field state is invalid")
        self.field = StructuralAssociationField.from_state(field_state)
        self._validate_cursor()

    def _payload(self) -> bytes:
        return _canonical_json(
            {
                "format": RUNTIME_FORMAT,
                "cursor": {
                    "count": self.cursor_count,
                    "observation_id": self.cursor_observation_id,
                },
                "field": self.field.export_state(),
            }
        )

    def _checkpoint(self) -> StructuralAssociationStateReceipt:
        receipt = self.persistence.store(self._payload())
        pointer = {
            "format": POINTER_FORMAT,
            "receipt": receipt.as_dict(),
            "cursor": {
                "count": self.cursor_count,
                "observation_id": self.cursor_observation_id,
            },
        }
        tmp = self.pointer_path.with_suffix(".json.tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(pointer, ensure_ascii=False, sort_keys=True, indent=2))
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.pointer_path)
        return receipt

    def sync(self) -> int:
        with self._lock:
            self._validate_cursor()
            pending = self.observations.ordered_from(self.cursor_count)
            if not pending and self.pointer_path.is_file():
                return 0
            for envelope in pending:
                self.field.observe(envelope)
                self.cursor_count += 1
                self.cursor_observation_id = str(envelope["observation_id"])
            self._checkpoint()
            return len(pending)

    def association(
        self,
        hierarchy_id: str,
        source: int,
        target: int,
        *,
        channel: str | None = None,
    ) -> float:
        """Read one decayed association through the runtime lock."""
        with self._lock:
            return self.field.association(
                hierarchy_id,
                source,
                target,
                channel=channel,
            )

    def strongest(
        self,
        hierarchy_id: str,
        source: int,
        *,
        channel: str | None = None,
        top_k: int = 10,
    ):
        with self._lock:
            return self.field.strongest(
                hierarchy_id,
                source,
                channel=channel,
                top_k=top_k,
            )

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": RUNTIME_FORMAT,
                "backend": self.persistence.last_backend or self.persistence.backend or "auto",
                "cursor": {
                    "count": self.cursor_count,
                    "observation_id": self.cursor_observation_id,
                },
                "raw_observations": self.observations.count,
                "pending_observations": self.observations.count - self.cursor_count,
                "replayed_on_open": self.replayed_on_open,
                "derived_observations": self.field.observation_count,
                "derived_edges": self.field.edge_count,
                "hierarchies": self.field.hierarchy_count,
                "semantic_projection": False,
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "schema": RUNTIME_FORMAT,
                "backend": self.persistence.last_backend or self.persistence.backend or "auto",
                "cursor": {
                    "count": self.cursor_count,
                    "observation_id": self.cursor_observation_id,
                },
                "raw_observations": self.observations.count,
                "pending_observations": self.observations.count - self.cursor_count,
                "replayed_on_open": self.replayed_on_open,
                "field": self.field.snapshot(),
            }
