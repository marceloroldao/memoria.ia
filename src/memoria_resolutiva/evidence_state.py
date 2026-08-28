from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path

from .bdr_store import BDRResolutiveMemory
from .evidence_core import EvidenceCore
from .sqlite_store import SQLiteResolutiveMemory
from .storage_backend import open_resolutive_memory

EVIDENCE_STATE_FORMAT = "memoria.ia-evidence-core-v1"


@dataclass(frozen=True, slots=True)
class EvidenceStateReceipt:
    backend: str
    state_id: str
    sha256: str

    def as_dict(self) -> dict[str, str]:
        return {"backend": self.backend, "state_id": self.state_id, "sha256": self.sha256}


class EvidenceCoreStateCodec:
    """Canonical, replay-based state codec for the stable Evidence Core.

    Only source evidence and explicit reliability adjudications are serialized.
    Derived indexes, next-epoch counters, source reliability posteriors and the
    adjudication DAG are reconstructed by replay. This keeps persisted state
    deterministic and prevents implementation caches from becoming schema.
    """

    @staticmethod
    def dump(core: EvidenceCore) -> bytes:
        payload = {
            "format": EVIDENCE_STATE_FORMAT,
            "edges": [asdict(edge) for edge in core._edges],
            "adjudications": [asdict(record) for record in core._adjudications],
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def load(data: bytes) -> EvidenceCore:
        raw = json.loads(data.decode("utf-8"))
        if raw.get("format") != EVIDENCE_STATE_FORMAT:
            raise ValueError("unsupported Evidence Core state format")
        edges = raw.get("edges")
        adjudications = raw.get("adjudications")
        if not isinstance(edges, list) or not isinstance(adjudications, list):
            raise ValueError("invalid Evidence Core state payload")

        core = EvidenceCore()
        for row in edges:
            if not isinstance(row, dict):
                raise ValueError("invalid Evidence Core edge state")
            core.observe_relation(
                str(row["subject"]),
                str(row["predicate"]),
                str(row["object"]),
                evidence_id=str(row["evidence_id"]),
                source_text=str(row["source_text"]),
                provenance=str(row["provenance"]),
                origin=str(row["origin"]),
                confidence=float(row["confidence"]),
                namespace=row.get("namespace"),
                epoch=int(row["epoch"]),
            )
        for row in adjudications:
            if not isinstance(row, dict):
                raise ValueError("invalid Evidence Core adjudication state")
            core.adjudicate_origin(
                str(row["origin"]),
                resolution_id=str(row["resolution_id"]),
                confirmed=bool(row["confirmed"]),
                adjudicator_origins=tuple(str(item) for item in row["adjudicator_origins"]),
                weight=float(row["weight"]),
            )
        return core


class EvidenceCorePersistence:
    """Content-addressed Evidence Core durability over the v1 storage selector."""

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

    def store(self, core: EvidenceCore) -> EvidenceStateReceipt:
        payload = EvidenceCoreStateCodec.dump(core)
        digest = hashlib.sha256(payload).hexdigest()
        state_id = f"evidence-core:{digest}"
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
                raise ValueError("Evidence Core state id collision")
        finally:
            store.close()
        return EvidenceStateReceipt(backend_name, state_id, digest)

    def load(self, receipt: EvidenceStateReceipt | dict[str, str]) -> EvidenceCore:
        if isinstance(receipt, EvidenceStateReceipt):
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
            raise ValueError("Evidence Core persistence checksum mismatch")
        return EvidenceCoreStateCodec.load(payload)
