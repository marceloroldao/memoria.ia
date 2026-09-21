from __future__ import annotations

from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from threading import RLock

from .address_trajectory_conversation_v2 import (
    AddressTrajectoryConversationResolverV2,
    AddressTrajectoryResolveResultV2,
)
from .address_trajectory_v2 import AddressTrajectory, AddressTrajectoryMemory
from .product_persistence import ProductSnapshotPersistence


_SCHEMA = "memoria.address-trajectory.namespace.v2"


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


class PersistentAddressTrajectoryStoreV2:
    """Namespaced durable boundary for the experimental V2 trajectory memory.

    The cognitive representation stays AddressTrajectoryMemory. Persistence is a
    content-addressed snapshot written through ProductSnapshotPersistence, so Linux
    can use BDR while tests/fallback environments may use SQLite. A portable copy is
    retained only as a verified recovery path.

    No semantic parsing is introduced here. Namespace selection is storage
    isolation, not part of trajectory scoring.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        backend: str | None = None,
        allow_fallback: bool = True,
        resolver_limit: int = 8,
    ) -> None:
        if resolver_limit < 2:
            raise ValueError("resolver_limit must be >= 2")
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.persistence = ProductSnapshotPersistence(
            self.root / "persistence",
            backend=backend,
            allow_fallback=allow_fallback,
        )
        self.resolver_limit = resolver_limit
        self._cache: dict[str, AddressTrajectoryMemory] = {}
        self._lock = RLock()

    @staticmethod
    def _namespace(session_id: str | None) -> str:
        return "" if session_id is None else str(session_id)

    def _namespace_key(self, namespace: str) -> str:
        return sha256(namespace.encode("utf-8")).hexdigest()

    def _paths(self, namespace: str) -> tuple[Path, Path]:
        key = self._namespace_key(namespace)
        state = self.root / "namespaces"
        return state / f"{key}.snapshot.json", state / f"{key}.receipt.json"

    @staticmethod
    def _serialize(namespace: str, memory: AddressTrajectoryMemory) -> bytes:
        payload = {
            "schema": _SCHEMA,
            "namespace": namespace,
            "trajectories": [
                {
                    "trajectory_id": item.trajectory_id,
                    "raw_text": item.raw_text,
                    "addresses": list(item.addresses),
                    "surfaces": list(item.surfaces),
                }
                for item in memory.snapshot()
            ],
        }
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

    @staticmethod
    def _deserialize(payload: bytes, *, expected_namespace: str) -> AddressTrajectoryMemory:
        raw = json.loads(payload.decode("utf-8"))
        if raw.get("schema") != _SCHEMA:
            raise ValueError("unsupported V2 trajectory snapshot schema")
        if raw.get("namespace") != expected_namespace:
            raise ValueError("V2 trajectory snapshot namespace mismatch")

        rows = raw.get("trajectories")
        if not isinstance(rows, list):
            raise ValueError("V2 trajectory snapshot trajectories must be a list")

        trajectories: list[AddressTrajectory] = []
        seen_ids: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("invalid V2 trajectory snapshot row")
            trajectory_id = str(row.get("trajectory_id") or "")
            raw_text = str(row.get("raw_text") or "")
            addresses_raw = row.get("addresses")
            surfaces_raw = row.get("surfaces")
            if not trajectory_id or trajectory_id in seen_ids:
                raise ValueError("V2 trajectory snapshot IDs must be unique and non-empty")
            if not isinstance(addresses_raw, list) or not isinstance(surfaces_raw, list):
                raise ValueError("invalid V2 trajectory snapshot address/surface arrays")
            addresses = tuple(str(value) for value in addresses_raw)
            surfaces = tuple(str(value) for value in surfaces_raw)
            if not addresses or len(addresses) != len(surfaces):
                raise ValueError("invalid V2 trajectory snapshot geometry")
            if any(not value for value in addresses):
                raise ValueError("V2 trajectory addresses must be non-empty")
            seen_ids.add(trajectory_id)
            trajectories.append(
                AddressTrajectory(
                    trajectory_id=trajectory_id,
                    raw_text=raw_text,
                    addresses=addresses,
                    surfaces=surfaces,
                )
            )
        return AddressTrajectoryMemory.restore(tuple(trajectories))

    def _load_uncached(self, namespace: str) -> AddressTrajectoryMemory:
        snapshot_path, receipt_path = self._paths(namespace)
        if not receipt_path.exists():
            if snapshot_path.exists():
                raise ValueError("V2 trajectory portable snapshot exists without receipt")
            return AddressTrajectoryMemory()

        receipt_doc = json.loads(receipt_path.read_text("utf-8"))
        if receipt_doc.get("namespace") != namespace:
            raise ValueError("V2 trajectory receipt namespace mismatch")
        receipt = receipt_doc.get("persistence")
        if not isinstance(receipt, dict):
            raise ValueError("invalid V2 trajectory persistence receipt")
        payload = self.persistence.restore_or_portable_fallback(receipt, snapshot_path)
        return self._deserialize(payload, expected_namespace=namespace)

    def memory(self, session_id: str | None = None) -> AddressTrajectoryMemory:
        namespace = self._namespace(session_id)
        with self._lock:
            memory = self._cache.get(namespace)
            if memory is None:
                memory = self._load_uncached(namespace)
                self._cache[namespace] = memory
            return memory

    def save(self, session_id: str | None = None) -> dict[str, str]:
        namespace = self._namespace(session_id)
        with self._lock:
            memory = self.memory(session_id)
            payload = self._serialize(namespace, memory)
            receipt = self.persistence.store_bytes(payload)
            snapshot_path, receipt_path = self._paths(namespace)
            _atomic_write(snapshot_path, payload)
            receipt_payload = json.dumps(
                {
                    "schema": _SCHEMA,
                    "namespace": namespace,
                    "persistence": receipt.as_dict(),
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
            _atomic_write(receipt_path, receipt_payload)
            return receipt.as_dict()

    def ingest(self, text: str, *, session_id: str | None = None) -> AddressTrajectory:
        with self._lock:
            memory = self.memory(session_id)
            trajectory = memory.ingest(text)
            self.save(session_id)
            return trajectory

    def resolve(
        self,
        *,
        query: str,
        session_id: str | None = None,
    ) -> AddressTrajectoryResolveResultV2:
        with self._lock:
            memory = self.memory(session_id)
            return AddressTrajectoryConversationResolverV2(
                memory,
                limit=self.resolver_limit,
            ).resolve(query=query, session_id=session_id)

    def snapshot_bytes(self, session_id: str | None = None) -> bytes:
        namespace = self._namespace(session_id)
        with self._lock:
            return self._serialize(namespace, self.memory(session_id))

    @property
    def backend(self) -> str:
        return self.persistence.last_backend or self.persistence.backend or "auto"
