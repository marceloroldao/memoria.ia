from __future__ import annotations

import ctypes
from dataclasses import dataclass
import json
from pathlib import Path
import threading
import unicodedata

from .episodic_recall import EpisodicRecallResult
from .product_episodic import EpisodeRecallRequest, EpisodeStoreRequest


MEMORIA_MOBILE_ABI_VERSION = 1
MEMORIA_MOBILE_OK = 0
MEMORIA_MOBILE_INVALID_ARGUMENT = 1
MEMORIA_MOBILE_UNRESOLVED = 2


class _NativeBuffer(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("size", ctypes.c_size_t),
    ]


@dataclass(frozen=True, slots=True)
class NativeEpisodeEdge:
    evidence_id: str
    namespace: str | None


@dataclass(frozen=True, slots=True)
class NativeEpisodeReceipt:
    """Truthful durable-write receipt for the native BDR path.

    The mobile ABI currently guarantees a durable atomic write but does not expose
    the EvidenceCore snapshot state_id/sha256 contract. Those fields therefore
    remain explicitly unavailable instead of being synthesized.
    """

    backend: str = "bdr-native"
    durable: bool = True

    def as_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend,
            "state_id": None,
            "sha256": None,
            "durable": self.durable,
        }


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _normalized_topics(values: list[str]) -> tuple[str, ...]:
    return tuple(sorted({_key(value) for value in values if _key(value)}))


class NativeEpisodicService:
    """Thin Python boundary over the authoritative native episodic runtime.

    FastAPI/Pydantic stay in Python. Episodic persistence, candidate selection,
    ambiguity handling and recency resolution are delegated to libmemoria_mobile.
    No Python episodic algorithm is consulted as a fallback.
    """

    def __init__(
        self,
        *,
        library_path: str | Path,
        data_dir: str | Path,
        organization_id: str,
    ) -> None:
        self.library_path = Path(library_path)
        self.data_dir = Path(data_dir)
        self.organization_id = organization_id
        if not self.library_path.is_file():
            raise RuntimeError(f"native Memoria.ia library not found: {self.library_path}")
        if not organization_id.strip():
            raise RuntimeError("organization_id must be non-empty for native episodic runtime")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lib = ctypes.CDLL(str(self.library_path))
        self._configure_abi()
        if self._lib.memoria_mobile_abi_version() != MEMORIA_MOBILE_ABI_VERSION:
            raise RuntimeError("unsupported Memoria.ia native mobile ABI version")
        self._handle = ctypes.c_void_p()
        status = self._lib.memoria_mobile_open(
            str(self.data_dir).encode("utf-8"),
            organization_id.encode("utf-8"),
            ctypes.byref(self._handle),
        )
        if status != MEMORIA_MOBILE_OK or not self._handle.value:
            raise RuntimeError(f"failed to open native Memoria.ia runtime: status={status}")
        self._lock = threading.RLock()
        self._closed = False

    def _configure_abi(self) -> None:
        self._lib.memoria_mobile_abi_version.restype = ctypes.c_uint32
        self._lib.memoria_mobile_open.argtypes = [
            ctypes.c_char_p,
            ctypes.c_char_p,
            ctypes.POINTER(ctypes.c_void_p),
        ]
        self._lib.memoria_mobile_open.restype = ctypes.c_int
        self._lib.memoria_mobile_store_episode_json.argtypes = [
            ctypes.c_void_p,
            _NativeBuffer,
            ctypes.POINTER(_NativeBuffer),
        ]
        self._lib.memoria_mobile_store_episode_json.restype = ctypes.c_int
        self._lib.memoria_mobile_recall_episode_json.argtypes = [
            ctypes.c_void_p,
            _NativeBuffer,
            ctypes.POINTER(_NativeBuffer),
        ]
        self._lib.memoria_mobile_recall_episode_json.restype = ctypes.c_int
        self._lib.memoria_mobile_flush.argtypes = [ctypes.c_void_p]
        self._lib.memoria_mobile_flush.restype = ctypes.c_int
        self._lib.memoria_mobile_free_buffer.argtypes = [_NativeBuffer]
        self._lib.memoria_mobile_close.argtypes = [ctypes.c_void_p]

    def _call(self, function_name: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        if self._closed or not self._handle.value:
            raise RuntimeError("native episodic runtime is closed")
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        backing = ctypes.create_string_buffer(raw)
        request = _NativeBuffer(ctypes.cast(backing, ctypes.POINTER(ctypes.c_uint8)), len(raw))
        response = _NativeBuffer()
        with self._lock:
            status = getattr(self._lib, function_name)(self._handle, request, ctypes.byref(response))
            try:
                body = ctypes.string_at(response.data, response.size).decode("utf-8") if response.data else ""
            finally:
                if response.data:
                    self._lib.memoria_mobile_free_buffer(response)
        if not body:
            return status, {}
        try:
            decoded = json.loads(body)
        except json.JSONDecodeError as exc:
            raise RuntimeError("native Memoria.ia returned invalid JSON") from exc
        if not isinstance(decoded, dict):
            raise RuntimeError("native Memoria.ia returned a non-object JSON response")
        return status, decoded

    def store(self, request: EpisodeStoreRequest) -> tuple[NativeEpisodeEdge, NativeEpisodeReceipt]:
        if request.parent_memory_ids:
            raise ValueError(
                "native episodic parent lineage is not yet supported; refusing to drop provenance"
            )
        topics = _normalized_topics(request.topics)
        source_type = "user_assertion" if request.role == "user" else "assistant_generated"
        source_authority = 0.95 if request.role == "user" else 0.25
        payload: dict[str, object] = {
            "episode_id": request.episode_id,
            "session_id": request.session_id or "",
            "role": request.role,
            "text": request.text,
            "order": request.order,
            "timestamp": request.timestamp or "",
            "event_type": _key(request.event_type) if request.event_type else "",
            "topics_csv": ",".join(topics),
            "source_type": source_type,
            "source_authority": source_authority,
            "ultimate_source_memory_id": request.episode_id,
        }
        status, response = self._call("memoria_mobile_store_episode_json", payload)
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native episodic store rejected request"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "OK":
            raise RuntimeError(f"native episodic store failed: status={status}")
        if response.get("durable") is not True:
            raise RuntimeError("native episodic store did not confirm durable persistence")
        returned_id = str(response.get("episode_id") or "")
        if returned_id != request.episode_id:
            raise RuntimeError("native episodic store returned an unexpected episode_id")
        return NativeEpisodeEdge(request.episode_id, request.session_id), NativeEpisodeReceipt()

    def resolve(self, request: EpisodeRecallRequest) -> EpisodicRecallResult:
        topics = _normalized_topics(request.topics)
        payload: dict[str, object] = {
            "query": request.query,
            "session_id": request.session_id or "",
            "role": request.role or "",
            "event_type": _key(request.event_type) if request.event_type else "",
            "topics_csv": ",".join(topics),
        }
        status, response = self._call("memoria_mobile_recall_episode_json", payload)
        if status == MEMORIA_MOBILE_UNRESOLVED or response.get("status") == "UNRESOLVED":
            return EpisodicRecallResult("UNRESOLVED", 0.0, (), "", None, None, None, ())
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native episodic recall rejected request"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "HIT":
            raise RuntimeError(f"native episodic recall failed: status={status}")
        episode_ids = tuple(str(value) for value in response.get("episode_ids", []))
        topics_csv = str(response.get("topics_csv") or "")
        return EpisodicRecallResult(
            "HIT",
            float(response.get("confidence", 0.0)),
            episode_ids,
            str(response.get("selected_context") or ""),
            int(response["order"]) if response.get("order") is not None else None,
            str(response["timestamp"]) if response.get("timestamp") else None,
            str(response["event_type"]) if response.get("event_type") else None,
            tuple(value for value in topics_csv.split(",") if value),
            str(response["source_type"]) if response.get("source_type") else None,
            float(response["source_authority"]) if response.get("source_authority") is not None else None,
            str(response["ultimate_source_memory_id"]) if response.get("ultimate_source_memory_id") else None,
        )

    def flush(self) -> None:
        if self._closed or not self._handle.value:
            return
        with self._lock:
            status = self._lib.memoria_mobile_flush(self._handle)
        if status != MEMORIA_MOBILE_OK:
            raise RuntimeError(f"native Memoria.ia flush failed: status={status}")

    def close(self) -> None:
        if self._closed:
            return
        with self._lock:
            if self._handle.value:
                self._lib.memoria_mobile_close(self._handle)
                self._handle = ctypes.c_void_p()
            self._closed = True
