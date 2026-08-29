from __future__ import annotations

import ctypes
import hashlib
import json
from pathlib import Path
import threading

from .product_conversation import ConversationIngestResult, ConversationResolveResult


MEMORIA_MOBILE_ABI_VERSION = 1
MEMORIA_MOBILE_OK = 0
MEMORIA_MOBILE_INVALID_ARGUMENT = 1
MEMORIA_MOBILE_UNRESOLVED = 2
MAX_NATIVE_RELATIONS = 4


class _NativeBuffer(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("size", ctypes.c_size_t),
    ]


def _memory_id(*, role: str, text: str, session_id: str | None, order: int | None, index: int) -> str:
    raw = f"{session_id or ''}\0{order if order is not None else ''}\0{role}\0{text}\0{index}".encode("utf-8")
    return "conv:" + hashlib.sha256(raw).hexdigest()[:24]


def _relation_payload(row: object, *, namespace: str | None, order: int | None) -> dict[str, object]:
    if not isinstance(row, dict):
        raise RuntimeError("native Memoria.ia returned an invalid relation row")
    return {
        "subject": str(row.get("subject") or ""),
        "predicate": str(row.get("predicate") or ""),
        "object": str(row.get("object") or ""),
        "memory_id": str(row.get("memory_id") or ""),
        "confidence": float(row.get("confidence", 0.0)),
        "epoch": order,
        "namespace": namespace,
    }


class NativeConversationService:
    """Thin Python boundary over the authoritative native conversation runtime.

    HTTP, authentication and Pydantic stay in Python. Persistent memory,
    relation extraction, ranking, ambiguity, correction, temporal resolution and
    provenance authority are delegated to libmemoria_mobile. There is no Python
    semantic fallback.
    """

    def __init__(self, *, library_path: str | Path, data_dir: str | Path, organization_id: str) -> None:
        self.library_path = Path(library_path)
        self.data_dir = Path(data_dir)
        self.organization_id = organization_id
        if not self.library_path.is_file():
            raise RuntimeError(f"native Memoria.ia library not found: {self.library_path}")
        if not organization_id.strip():
            raise RuntimeError("organization_id must be non-empty for native conversation runtime")
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
        self._lib.memoria_mobile_open.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
        self._lib.memoria_mobile_open.restype = ctypes.c_int
        for name in ("memoria_mobile_learn_turn_json", "memoria_mobile_resolve_context_json"):
            function = getattr(self._lib, name)
            function.argtypes = [ctypes.c_void_p, _NativeBuffer, ctypes.POINTER(_NativeBuffer)]
            function.restype = ctypes.c_int
        self._lib.memoria_mobile_flush.argtypes = [ctypes.c_void_p]
        self._lib.memoria_mobile_flush.restype = ctypes.c_int
        self._lib.memoria_mobile_free_buffer.argtypes = [_NativeBuffer]
        self._lib.memoria_mobile_close.argtypes = [ctypes.c_void_p]

    def _call(self, function_name: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        if self._closed or not self._handle.value:
            raise RuntimeError("native conversation runtime is closed")
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

    def ingest(
        self,
        *,
        role: str,
        text: str,
        session_id: str | None = None,
        order: int | None = None,
        timestamp: str | None = None,
        parent_memory_ids: tuple[str, ...] | list[str] = (),
        corrects_memory_ids: tuple[str, ...] | list[str] = (),
    ) -> ConversationIngestResult:
        if role not in {"user", "assistant"}:
            raise ValueError("role must be 'user' or 'assistant'")
        if corrects_memory_ids and role != "user":
            raise ValueError("only user turns may explicitly correct prior memories")
        text = text.strip()
        if not text:
            raise ValueError("text must be non-empty")
        turn_id = _memory_id(role=role, text=text, session_id=session_id, order=order, index=-1)
        relation_ids = [
            _memory_id(role=role, text=text, session_id=session_id, order=order, index=index)
            for index in range(MAX_NATIVE_RELATIONS)
        ]
        source_type = "user_correction" if corrects_memory_ids else ("user_assertion" if role == "user" else "assistant_generated")
        if source_type == "user_correction":
            source_authority = 1.0
        elif source_type == "user_assertion":
            source_authority = 0.95
        else:
            source_authority = 0.25
        payload: dict[str, object] = {
            "role": role,
            "text": text,
            "memory_id": turn_id,
            "namespace": session_id or "",
            "source_type": source_type,
            "source_authority": source_authority,
            "timestamp": timestamp or "",
            "parent_memory_ids": list(parent_memory_ids),
            "corrects_memory_ids": list(corrects_memory_ids),
            "relation_memory_ids": relation_ids,
        }
        if order is not None:
            payload["order"] = order
        status, response = self._call("memoria_mobile_learn_turn_json", payload)
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native conversation ingest rejected request"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "OK":
            raise RuntimeError(f"native conversation ingest failed: status={status}")
        rows = response.get("relations", [])
        if not isinstance(rows, list):
            raise RuntimeError("native conversation ingest returned invalid relations")
        relations = tuple(_relation_payload(row, namespace=session_id, order=order) for row in rows)
        actual_relation_ids = tuple(str(row["memory_id"]) for row in relations if row.get("memory_id"))
        return ConversationIngestResult((turn_id, *actual_relation_ids), relations, not relations)

    def resolve(self, *, query: str, session_id: str | None = None) -> ConversationResolveResult:
        query = query.strip()
        if not query:
            raise ValueError("query must be non-empty")
        status, response = self._call(
            "memoria_mobile_resolve_context_json",
            {"query": query, "namespace": session_id or ""},
        )
        if status == MEMORIA_MOBILE_UNRESOLVED or response.get("status") == "UNRESOLVED":
            return ConversationResolveResult("UNRESOLVED", 0.0, (), "", (), ())
        if status == MEMORIA_MOBILE_INVALID_ARGUMENT:
            raise ValueError(str(response.get("reason") or "native conversation resolve rejected request"))
        if status != MEMORIA_MOBILE_OK or response.get("status") != "HIT":
            raise RuntimeError(f"native conversation resolve failed: status={status}")

        rows = response.get("relations", [])
        if not isinstance(rows, list):
            raise RuntimeError("native conversation resolve returned invalid relations")
        relations = tuple(_relation_payload(row, namespace=session_id, order=None) for row in rows)
        native_memory_ids = tuple(str(value) for value in response.get("memory_ids", []))

        provenance_rows: list[dict[str, object]] = []
        raw_provenance = response.get("provenance", [])
        if not isinstance(raw_provenance, list):
            raise RuntimeError("native conversation resolve returned invalid provenance")
        for row in raw_provenance:
            if not isinstance(row, dict):
                raise RuntimeError("native conversation resolve returned invalid provenance row")
            source_type = str(row.get("source_type") or "")
            provenance_rows.append({
                "memory_id": str(row.get("memory_id") or ""),
                "source_type": source_type,
                "source_authority": float(row.get("source_authority", 0.0)),
                "immediate_source_type": str(row.get("immediate_source_type") or source_type),
                "parent_memory_ids": list(row.get("parent_memory_ids") or []),
                "ultimate_source_memory_id": str(row.get("ultimate_source_memory_id") or row.get("memory_id") or ""),
                "created_order": row.get("created_order"),
                "created_time": row.get("created_time"),
                "superseded_by": row.get("superseded_by"),
            })

        # The native resolver ranks authoritative turns. The historic product API,
        # however, exposes the derived relation ID for a single-relation factual HIT.
        # This is identity normalization only: native extraction/ranking already chose
        # the source. We deliberately do not guess when multiple relations/sources exist.
        public_memory_ids = native_memory_ids
        if len(native_memory_ids) == 1 and len(relations) == 1:
            relation_id = str(relations[0].get("memory_id") or "")
            if relation_id and relation_id != native_memory_ids[0]:
                turn_id = native_memory_ids[0]
                public_memory_ids = (relation_id,)
                if len(provenance_rows) == 1:
                    provenance_rows[0]["memory_id"] = relation_id
                    provenance_rows[0]["immediate_source_type"] = "derived_relation"
                    provenance_rows[0]["parent_memory_ids"] = [turn_id]

        return ConversationResolveResult(
            "HIT",
            float(response.get("confidence", 0.0)),
            public_memory_ids,
            str(response.get("selected_context") or ""),
            relations,
            tuple(provenance_rows),
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
