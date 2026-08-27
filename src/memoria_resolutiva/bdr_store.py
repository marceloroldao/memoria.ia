from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock

try:
    from ._bdr_native import Database as _NativeDatabase
except ImportError as exc:  # pragma: no cover - exercised by fallback environments
    _NativeDatabase = None
    _NATIVE_IMPORT_ERROR = exc
else:
    _NATIVE_IMPORT_ERROR = None


_META_PREFIX = "meta:"
_META_MEMORIES = _META_PREFIX + "memories"
_META_NODES = _META_PREFIX + "unique_nodes"
_META_OCCURRENCES = _META_PREFIX + "occurrences"


def native_bdr_available() -> bool:
    return _NativeDatabase is not None


def _decode_u64(value: bytes | None) -> int:
    return 0 if value is None else int(value.decode("ascii"))


@dataclass(frozen=True)
class BDRPolicy:
    reserve_bytes: int = 64 * 1024 * 1024
    wal_batch: int = 512
    sync_every_memories: int = 1


class BDRResolutiveMemory:
    """Resolutive memory persisted directly in frozen BDR v1.0.0.

    On the BDR path, one logical add crosses Python/C++ once. Fragmentation,
    BLAKE2b node addressing, deduplication, occurrence construction, metadata
    updates and BDR puts are fused inside the native extension. Python remains
    the public API/orchestration layer.

    Writes are serialized inside one Python process. Cross-process multi-writer
    use remains intentionally unsupported until the storage layer exposes an
    atomic logical batch primitive.
    """

    def __init__(self, path: str | Path, max_layer: int = 3, *, policy: BDRPolicy | None = None):
        if _NativeDatabase is None:
            raise RuntimeError(
                "BDR native extension is unavailable; build with MEMORIA_BUILD_BDR=1 "
                "against frozen Resolutive-DB v1.0.0"
            ) from _NATIVE_IMPORT_ERROR

        self.path = str(path)
        self.max_layer = max_layer
        self.policy = policy or BDRPolicy()
        if self.policy.sync_every_memories < 1:
            raise ValueError("sync_every_memories must be >= 1")

        self._lock = RLock()
        Path(self.path).mkdir(parents=True, exist_ok=True)
        self.db = _NativeDatabase(self.path, self.policy.reserve_bytes, self.policy.wal_batch)
        self._pending_memories = 0
        self._memories = self._meta_get(_META_MEMORIES)
        self._unique_nodes = self._meta_get(_META_NODES)
        self._occurrences = self._meta_get(_META_OCCURRENCES)
        self._nodes_per_layer = {
            layer: self._meta_get(f"{_META_PREFIX}nodes_layer:{layer}")
            for layer in range(self.max_layer + 1)
        }

    def _meta_get(self, key: str) -> int:
        return _decode_u64(self.db.get(key))

    @staticmethod
    def _memory_key(memory_id: str) -> str:
        return "m:" + memory_id

    def add(self, memory_id: str, data: bytes) -> None:
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be bytes-like")
        payload_bytes = bytes(data)

        with self._lock:
            self._pending_memories += 1
            durable = self._pending_memories >= self.policy.sync_every_memories
            try:
                result = self.db.add_resolutive_memory(
                    memory_id, payload_bytes, self.max_layer, durable=durable
                )
            except RuntimeError as exc:
                if str(exc).startswith("memory already exists:"):
                    raise ValueError(str(exc)) from exc
                raise

            if durable:
                self._pending_memories = 0

            self._memories = int(result["memories"])
            self._unique_nodes = int(result["unique_nodes"])
            self._occurrences = int(result["occurrences"])
            self._nodes_per_layer = {
                int(layer): int(count)
                for layer, count in result["nodes_per_layer"].items()
            }

    def reconstruct(self, memory_id: str) -> bytes:
        value = self.db.get(self._memory_key(memory_id))
        if value is None:
            raise KeyError(memory_id)
        return bytes(value)

    def stats(self) -> dict:
        with self._lock:
            return {
                "memories": self._memories,
                "unique_nodes": self._unique_nodes,
                "occurrences": self._occurrences,
                "nodes_per_layer": dict(self._nodes_per_layer),
            }

    def flush(self) -> None:
        with self._lock:
            if self._pending_memories:
                self.db.sync()
                self._pending_memories = 0

    def checkpoint(self) -> None:
        with self._lock:
            self.flush()
            self.db.checkpoint()

    def close(self) -> None:
        with self._lock:
            if getattr(self, "db", None) is None:
                return
            self.flush()
            self.db.close()
            self.db = None

    def __enter__(self) -> "BDRResolutiveMemory":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
