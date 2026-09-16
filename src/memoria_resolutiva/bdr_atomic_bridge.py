from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Iterable


BDR_ATOMIC_C_OK = 0
BDR_ATOMIC_C_NOT_FOUND = 2
BDR_ATOMIC_C_PUT = 1
BDR_ATOMIC_C_DELETE = 2


class BDRBridgeError(RuntimeError):
    pass


class _Operation(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("key", ctypes.c_void_p),
        ("key_size", ctypes.c_size_t),
        ("value", ctypes.c_void_p),
        ("value_size", ctypes.c_size_t),
    ]


class _Buffer(ctypes.Structure):
    _fields_ = [
        ("data", ctypes.POINTER(ctypes.c_uint8)),
        ("size", ctypes.c_size_t),
    ]


class _BatchResult(ctypes.Structure):
    _fields_ = [
        ("sequence", ctypes.c_uint64),
        ("operations", ctypes.c_size_t),
        ("durable", ctypes.c_int),
    ]


class CtypesAtomicBDR:
    """Thin experimental Python binding over BDR's atomic C ABI v1.

    This class owns no persistence semantics. Atomicity, sequence and recovery
    remain entirely owned by BDR AtomicDatabase/BDW4.
    """

    def __init__(self, root: str | Path, library_path: str | Path) -> None:
        self.root = Path(root)
        self.library_path = Path(library_path)
        self._lib = ctypes.CDLL(str(self.library_path))
        self._configure_abi()
        if self._lib.bdr_atomic_c_abi_version() != 1:
            raise BDRBridgeError("unsupported BDR atomic C ABI version")
        self._handle = ctypes.c_void_p()
        self.root.mkdir(parents=True, exist_ok=True)
        status = self._lib.bdr_atomic_c_open(os.fsencode(self.root), ctypes.byref(self._handle))
        self._check(status, "open")
        if not self._handle.value:
            raise BDRBridgeError("BDR returned a null handle")

    def _configure_abi(self) -> None:
        lib = self._lib
        lib.bdr_atomic_c_abi_version.restype = ctypes.c_uint32
        lib.bdr_atomic_c_open.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)]
        lib.bdr_atomic_c_open.restype = ctypes.c_int
        lib.bdr_atomic_c_write_batch.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(_Operation),
            ctypes.c_size_t,
            ctypes.POINTER(_BatchResult),
        ]
        lib.bdr_atomic_c_write_batch.restype = ctypes.c_int
        lib.bdr_atomic_c_get.argtypes = [
            ctypes.c_void_p,
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.POINTER(_Buffer),
        ]
        lib.bdr_atomic_c_get.restype = ctypes.c_int
        lib.bdr_atomic_c_last_sequence.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
        lib.bdr_atomic_c_last_sequence.restype = ctypes.c_int
        lib.bdr_atomic_c_durable_sequence.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint64)]
        lib.bdr_atomic_c_durable_sequence.restype = ctypes.c_int
        lib.bdr_atomic_c_sync.argtypes = [ctypes.c_void_p]
        lib.bdr_atomic_c_sync.restype = ctypes.c_int
        lib.bdr_atomic_c_free_buffer.argtypes = [_Buffer]
        lib.bdr_atomic_c_close.argtypes = [ctypes.c_void_p]

    @staticmethod
    def _check(status: int, operation: str) -> None:
        if status != BDR_ATOMIC_C_OK:
            raise BDRBridgeError(f"BDR {operation} failed with status={status}")

    def write_batch(self, puts: Iterable[tuple[str | bytes, bytes]]) -> int:
        items = list(puts)
        if not items:
            raise ValueError("atomic BDR batch must contain at least one operation")
        operations = (_Operation * len(items))()
        keepalive: list[ctypes.Array] = []
        for index, (key, value) in enumerate(items):
            key_bytes = key.encode("utf-8") if isinstance(key, str) else bytes(key)
            value_bytes = bytes(value)
            if not key_bytes:
                raise ValueError("BDR keys must be non-empty")
            key_buffer = ctypes.create_string_buffer(key_bytes)
            value_buffer = ctypes.create_string_buffer(value_bytes)
            keepalive.extend((key_buffer, value_buffer))
            operations[index] = _Operation(
                BDR_ATOMIC_C_PUT,
                ctypes.cast(key_buffer, ctypes.c_void_p),
                len(key_bytes),
                ctypes.cast(value_buffer, ctypes.c_void_p),
                len(value_bytes),
            )
        result = _BatchResult()
        self._check(
            self._lib.bdr_atomic_c_write_batch(
                self._handle,
                operations,
                len(items),
                ctypes.byref(result),
            ),
            "write_batch",
        )
        if result.operations != len(items) or result.durable != 1:
            raise BDRBridgeError("BDR returned an incomplete or non-durable logical batch")
        return int(result.sequence)

    def get(self, key: str | bytes) -> bytes | None:
        key_bytes = key.encode("utf-8") if isinstance(key, str) else bytes(key)
        if not key_bytes:
            raise ValueError("BDR keys must be non-empty")
        key_buffer = ctypes.create_string_buffer(key_bytes)
        out = _Buffer()
        status = self._lib.bdr_atomic_c_get(
            self._handle,
            ctypes.cast(key_buffer, ctypes.c_void_p),
            len(key_bytes),
            ctypes.byref(out),
        )
        if status == BDR_ATOMIC_C_NOT_FOUND:
            return None
        self._check(status, "get")
        try:
            return ctypes.string_at(out.data, out.size) if out.size else b""
        finally:
            self._lib.bdr_atomic_c_free_buffer(out)

    def last_sequence(self) -> int:
        value = ctypes.c_uint64()
        self._check(self._lib.bdr_atomic_c_last_sequence(self._handle, ctypes.byref(value)), "last_sequence")
        return int(value.value)

    def durable_sequence(self) -> int:
        value = ctypes.c_uint64()
        self._check(
            self._lib.bdr_atomic_c_durable_sequence(self._handle, ctypes.byref(value)),
            "durable_sequence",
        )
        return int(value.value)

    def sync(self) -> None:
        self._check(self._lib.bdr_atomic_c_sync(self._handle), "sync")

    def close(self) -> None:
        if getattr(self, "_handle", None) is not None and self._handle.value:
            self._lib.bdr_atomic_c_close(self._handle)
            self._handle = ctypes.c_void_p()

    def __enter__(self) -> "CtypesAtomicBDR":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
