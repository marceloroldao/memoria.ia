from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path

from .bdr_store import BDRResolutiveMemory
from .sqlite_store import SQLiteResolutiveMemory
from .storage_backend import open_resolutive_memory


@dataclass(frozen=True, slots=True)
class StateSnapshotReceipt:
    backend: str
    state_id: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {
            "backend": self.backend,
            "state_id": self.state_id,
            "sha256": self.sha256,
        }


class ContentAddressedStatePersistence:
    """Content-addressed durability primitive for post-RC1 cognitive state."""

    def __init__(
        self,
        root: str | Path,
        *,
        namespace: str,
        backend: str | None = None,
        allow_fallback: bool = True,
    ) -> None:
        normalized = str(namespace).strip()
        if not normalized:
            raise ValueError("namespace must be non-empty")
        self.root = Path(root)
        self.namespace = normalized
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

    def store_bytes(self, payload: bytes) -> StateSnapshotReceipt:
        raw = bytes(payload)
        digest = hashlib.sha256(raw).hexdigest()
        state_id = f"{self.namespace}:{digest}"
        store = self._open()
        backend_name = self._backend_name(store)
        try:
            try:
                existing = store.reconstruct(state_id)
            except KeyError:
                existing = None
            if existing is None:
                store.add(state_id, raw)
            elif existing != raw:
                raise ValueError("content-addressed cognitive state collision")
        finally:
            store.close()
        return StateSnapshotReceipt(backend_name, state_id, digest)

    def load_bytes(self, receipt: StateSnapshotReceipt | dict[str, str]) -> bytes:
        if isinstance(receipt, StateSnapshotReceipt):
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
            raise ValueError("cognitive state checksum mismatch")
        return payload
