from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from .layers import layer_bits
from .node import digest_payload

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


def _u64(value: int) -> bytes:
    return str(int(value)).encode("ascii")


def _decode_u64(value: bytes | None) -> int:
    return 0 if value is None else int(value.decode("ascii"))


@dataclass(frozen=True)
class BDRPolicy:
    reserve_bytes: int = 64 * 1024 * 1024
    wal_batch: int = 512
    # 1 is the default because it gives a durable boundary after each logical
    # memory while still being much faster than the current SQLite path.
    # Values >1 are an explicit high-performance mode until BDR gains atomic
    # batch commit semantics.
    sync_every_memories: int = 1


class BDRResolutiveMemory:
    """Resolutive memory persisted directly in frozen BDR v1.0.0.

    The hot persistence path crosses Python/C++ once per logical memory through
    put_many(). A single sync boundary is used for the configured number of
    logical memories; checkpoint is deliberately explicit because direct-native
    stress tests showed it is much more expensive than normal BDR sync/recovery.

    Writes are serialized inside one Python process so memory/node/occurrence
    counters cannot race. Cross-process multi-writer use is intentionally not
    supported by this integration layer yet.
    """

    def __init__(
        self,
        path: str | Path,
        max_layer: int = 3,
        *,
        policy: BDRPolicy | None = None,
    ):
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
        self.db = _NativeDatabase(
            self.path,
            self.policy.reserve_bytes,
            self.policy.wal_batch,
        )
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

    def _chunks(self, data: bytes, layer: int):
        width = layer_bits(layer) // 8
        for offset in range(0, len(data), width):
            yield offset // width, data[offset : offset + width]

    @staticmethod
    def _memory_key(memory_id: str) -> str:
        return "m:" + memory_id

    @staticmethod
    def _node_key(node_id: str) -> str:
        return "n:" + node_id

    @staticmethod
    def _occurrence_key(memory_id: str, layer: int, local_time: int) -> str:
        return f"o:{memory_id}:{layer}:{local_time}"

    def add(self, memory_id: str, data: bytes) -> None:
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("data must be bytes-like")
        payload_bytes = bytes(data)

        with self._lock:
            memory_key = self._memory_key(memory_id)
            if self.db.contains(memory_key):
                raise ValueError(f"memory already exists: {memory_id}")

            node_candidates: dict[str, tuple[int, bytes]] = {}
            occurrences: list[tuple[str, bytes]] = []
            for layer in range(self.max_layer + 1):
                for local_time, payload in self._chunks(payload_bytes, layer):
                    if not payload:
                        continue
                    node_id = digest_payload(payload, layer)
                    node_key = self._node_key(node_id)
                    node_candidates.setdefault(node_key, (layer, payload))
                    occurrences.append(
                        (self._occurrence_key(memory_id, layer, local_time), node_id.encode("ascii"))
                    )

            candidate_keys = list(node_candidates)
            existing = self.db.contains_many(candidate_keys) if candidate_keys else []
            new_nodes: list[tuple[str, bytes]] = []
            added_per_layer = {layer: 0 for layer in range(self.max_layer + 1)}
            for key, already_exists in zip(candidate_keys, existing):
                if already_exists:
                    continue
                layer, payload = node_candidates[key]
                # Keep the same logical information represented by the SQLite columns.
                value = layer.to_bytes(2, "big") + payload
                new_nodes.append((key, value))
                added_per_layer[layer] += 1

            next_memories = self._memories + 1
            next_nodes = self._unique_nodes + len(new_nodes)
            next_occurrences = self._occurrences + len(occurrences)
            next_per_layer = {
                layer: self._nodes_per_layer[layer] + added_per_layer[layer]
                for layer in range(self.max_layer + 1)
            }

            batch: list[tuple[str, bytes]] = [(memory_key, payload_bytes)]
            batch.extend(new_nodes)
            batch.extend(occurrences)
            batch.extend(
                [
                    (_META_MEMORIES, _u64(next_memories)),
                    (_META_NODES, _u64(next_nodes)),
                    (_META_OCCURRENCES, _u64(next_occurrences)),
                ]
            )
            batch.extend(
                (f"{_META_PREFIX}nodes_layer:{layer}", _u64(count))
                for layer, count in next_per_layer.items()
            )

            self._pending_memories += 1
            durable = self._pending_memories >= self.policy.sync_every_memories
            self.db.put_many(batch, durable=durable)
            if durable:
                self._pending_memories = 0

            self._memories = next_memories
            self._unique_nodes = next_nodes
            self._occurrences = next_occurrences
            self._nodes_per_layer = next_per_layer

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
