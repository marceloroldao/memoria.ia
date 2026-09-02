from __future__ import annotations

import ctypes
import json
from pathlib import Path
import threading


MEMORIA_MOBILE_ABI_VERSION = 1
MEMORIA_MOBILE_OK = 0


class NativeBuffer(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("size", ctypes.c_size_t),
    ]


class NativeRuntime:
    """Own one libmemoria_mobile handle for one durable native store."""

    def __init__(self, *, library_path: Path, data_dir: Path, organization_id: str) -> None:
        self.library_path = library_path
        self.data_dir = data_dir
        self.organization_id = organization_id
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._lib = ctypes.CDLL(str(self.library_path))
        self._configure_abi()
        if self._lib.memoria_mobile_abi_version() != MEMORIA_MOBILE_ABI_VERSION:
            raise RuntimeError("unsupported Memoria.ia native mobile ABI version")
        self._handle = ctypes.c_void_p()
        status = self._lib.memoria_mobile_open(
            str(self.data_dir).encode("utf-8"),
            self.organization_id.encode("utf-8"),
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
        for name in (
            "memoria_mobile_learn_turn_json",
            "memoria_mobile_resolve_context_json",
            "memoria_mobile_store_episode_json",
            "memoria_mobile_recall_episode_json",
            "memoria_mobile_export_snapshot_json",
        ):
            function = getattr(self._lib, name)
            function.argtypes = [ctypes.c_void_p, NativeBuffer, ctypes.POINTER(NativeBuffer)]
            function.restype = ctypes.c_int
        self._lib.memoria_mobile_flush.argtypes = [ctypes.c_void_p]
        self._lib.memoria_mobile_flush.restype = ctypes.c_int
        self._lib.memoria_mobile_free_buffer.argtypes = [NativeBuffer]
        self._lib.memoria_mobile_close.argtypes = [ctypes.c_void_p]

    @property
    def closed(self) -> bool:
        return self._closed

    def call(self, function_name: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        if self._closed or not self._handle.value:
            raise RuntimeError("native Memoria.ia runtime is closed")
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        backing = ctypes.create_string_buffer(raw)
        request = NativeBuffer(ctypes.cast(backing, ctypes.POINTER(ctypes.c_uint8)), len(raw))
        response = NativeBuffer()
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


class NativeRuntimeLease:
    def __init__(self, manager: "NativeRuntimeManager", key: tuple[str, str, str], runtime: NativeRuntime) -> None:
        self._manager = manager
        self._key = key
        self.runtime = runtime
        self._released = False

    def call(self, function_name: str, payload: dict[str, object]) -> tuple[int, dict[str, object]]:
        if self._released:
            raise RuntimeError("native Memoria.ia runtime lease is released")
        return self.runtime.call(function_name, payload)

    def flush(self) -> None:
        if not self._released:
            self.runtime.flush()

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._manager._release(self._key)


class NativeRuntimeManager:
    """Reference-count native handles and forbid conflicting DLLs per store."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[tuple[str, str, str], tuple[NativeRuntime, int]] = {}
        self._store_libraries: dict[tuple[str, str], str] = {}

    @staticmethod
    def _canonical_path(value: str | Path) -> Path:
        return Path(value).expanduser().resolve()

    def acquire(
        self,
        *,
        library_path: str | Path,
        data_dir: str | Path,
        organization_id: str,
    ) -> NativeRuntimeLease:
        library = self._canonical_path(library_path)
        data = self._canonical_path(data_dir)
        organization = organization_id.strip()
        if not library.is_file():
            raise RuntimeError(f"native Memoria.ia library not found: {library}")
        if not organization:
            raise RuntimeError("organization_id must be non-empty for native runtime")
        key = (str(library), str(data), organization)
        store_key = (str(data), organization)
        with self._lock:
            active_library = self._store_libraries.get(store_key)
            if active_library is not None and active_library != str(library):
                raise RuntimeError("native store is already open with a different Memoria.ia library")
            current = self._entries.get(key)
            if current is not None:
                runtime, references = current
                self._entries[key] = (runtime, references + 1)
                return NativeRuntimeLease(self, key, runtime)
            runtime = NativeRuntime(library_path=library, data_dir=data, organization_id=organization)
            self._entries[key] = (runtime, 1)
            self._store_libraries[store_key] = str(library)
            return NativeRuntimeLease(self, key, runtime)

    def _release(self, key: tuple[str, str, str]) -> None:
        with self._lock:
            current = self._entries.get(key)
            if current is None:
                return
            runtime, references = current
            if references > 1:
                self._entries[key] = (runtime, references - 1)
                return
            runtime.close()
            del self._entries[key]
            self._store_libraries.pop((key[1], key[2]), None)

    def active_runtime_count(self) -> int:
        with self._lock:
            return len(self._entries)


_DEFAULT_RUNTIME_MANAGER = NativeRuntimeManager()


def default_native_runtime_manager() -> NativeRuntimeManager:
    return _DEFAULT_RUNTIME_MANAGER()
